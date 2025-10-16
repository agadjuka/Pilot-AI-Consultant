from typing import List, Dict
from sqlalchemy.orm import Session
import google.generativeai as genai
from google.generativeai import protos
from datetime import datetime, timedelta
import logging
import json
import re
from app.repositories.dialog_history_repository import DialogHistoryRepository
from app.repositories.service_repository import ServiceRepository
from app.repositories.master_repository import MasterRepository
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.client_repository import ClientRepository
from app.services.llm_service import get_llm_service
from app.services.appointment_service import AppointmentService
from app.services.tool_service import ToolService
from app.services.google_calendar_service import GoogleCalendarService
from app.services.prompt_builder_service import PromptBuilderService
from app.core.dialogue_pattern_loader import dialogue_patterns
from app.services.dialogue_tracer_service import DialogueTracer
from app.core.logging_config import log_dialog_start, log_dialog_end, log_error

# Получаем логгер для этого модуля
logger = logging.getLogger(__name__)


class DialogService:
    """
    Оркестратор диалоговой логики.
    Координирует работу между хранилищем истории диалогов и AI-моделью.
    Реализует двухэтапную архитектуру: Классификация -> Мышление и Речь (итеративный цикл).
    """
    
    # Размер окна контекста - последние N сообщений
    CONTEXT_WINDOW_SIZE = 12
    
    def __init__(self, db_session: Session):
        """
        Инициализирует сервис диалога.
        
        Args:
            db_session: Сессия базы данных SQLAlchemy
        """
        self.repository = DialogHistoryRepository(db_session)
        self.llm_service = get_llm_service()
        
        # Инициализируем PromptBuilderService
        self.prompt_builder = PromptBuilderService()
        
        # Инициализируем репозитории для ToolService
        self.service_repository = ServiceRepository(db_session)
        self.master_repository = MasterRepository(db_session)
        self.appointment_repository = AppointmentRepository(db_session)
        self.client_repository = ClientRepository(db_session)
        
        # Инициализируем Google Calendar Service
        self.google_calendar_service = GoogleCalendarService()
        
        # Создаем экземпляр AppointmentService
        self.appointment_service = AppointmentService(
            appointment_repository=self.appointment_repository,
            client_repository=self.client_repository,
            master_repository=self.master_repository,
            service_repository=self.service_repository,
            google_calendar_service=self.google_calendar_service
        )
        
        # Создаем экземпляр ToolService
        self.tool_service = ToolService(
            service_repository=self.service_repository,
            master_repository=self.master_repository,
            appointment_service=self.appointment_service,
            google_calendar_service=self.google_calendar_service
        )
        
        # Создаем экземпляр ToolOrchestratorService для выполнения одиночных инструментов
        from app.services.tool_orchestrator_service import ToolOrchestratorService
        self.tool_orchestrator = ToolOrchestratorService(
            llm_service=self.llm_service,
            tool_service=self.tool_service,
            prompt_builder=self.prompt_builder,
            client_repository=self.client_repository
        )
        
        # Кратковременная память о контексте сессий для каждого пользователя
        # Формат: {user_id: {"appointments_in_focus": [{"id": int, "details": str}, ...], ...}}
        self.session_contexts = {}
    

    def parse_stage(self, stage_str: str) -> str:
        """
        Парсит ответ LLM на этапе классификации и извлекает стадию.
        
        Args:
            stage_str: Строка ответа от LLM
            
        Returns:
            ID стадии диалога
        """
        # Очищаем ответ от лишних символов и переносов строк
        cleaned_response = stage_str.strip()
        
        # Ищем стадию в первой строке ответа
        first_line = cleaned_response.split('\n')[0].strip().lower()
        
        # Проверяем, есть ли стадия в списке доступных
        if first_line in self.prompt_builder.dialogue_patterns:
            logger.info(f"✅ Стадия успешно определена: '{first_line}'")
            return first_line
        
        # Дополнительная проверка: ищем стадию в любом месте ответа
        for stage in self.prompt_builder.dialogue_patterns.keys():
            if stage in cleaned_response.lower():
                logger.info(f"✅ Стадия найдена в тексте: '{stage}'")
                return stage
        
        # Fallback на случай неверного ответа
        logger.warning(f"⚠️ Неизвестная стадия в ответе '{cleaned_response}', используем fallback")
        logger.warning(f"⚠️ Первая строка: '{first_line}'")
        return 'fallback'
    
    def parse_tool_calls(self, planning_response_json: str) -> List[Dict]:
        """
        Парсит JSON-ответ от LLM на этапе планирования и извлекает вызовы инструментов.
        
        Args:
            planning_response_json: JSON-строка с вызовами инструментов
            
        Returns:
            Список вызовов инструментов
        """
        try:
            # Удаляем markdown блоки если они есть
            cleaned_response = planning_response_json.strip()
            if cleaned_response.startswith('```') and cleaned_response.endswith('```'):
                cleaned_response = cleaned_response[3:-3].strip()
            elif cleaned_response.startswith('```json'):
                cleaned_response = cleaned_response[7:-3].strip()
            
            parsed_response = json.loads(cleaned_response)
            
            # Проверяем формат ответа
            if isinstance(parsed_response, dict) and 'tool_calls' in parsed_response:
                return parsed_response.get('tool_calls', [])
            elif isinstance(parsed_response, list):
                # Старый формат: [{"tool_name": "...", "parameters": {...}}]
                return parsed_response
            
            logger.warning(f"⚠️ Неожиданный формат ответа планирования: {parsed_response}")
            return []
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ Ошибка парсинга JSON ответа планирования: {e}")
            logger.error(f"❌ Сырой ответ: '{planning_response_json}'")
            return []
    
    def parse_hybrid_response(self, hybrid_response: str) -> tuple[str, List[Dict]]:
        """
        Парсит гибридный ответ LLM (JSON + текст) и извлекает вызовы инструментов.
        
        Args:
            hybrid_response: Сырой ответ от LLM
            
        Returns:
            Кортеж (очищенный_текст_для_пользователя, список_вызовов_инструментов)
        """
        import re
        
        # Ищем все блоки ``` ... ``` в ответе (с json или без)
        json_blocks = re.findall(r'```(?:json)?\s*([\s\S]*?)\s*```', hybrid_response)
        
        logger.info(f"🔍 Найдено JSON-блоков: {len(json_blocks)}")
        
        if not json_blocks:
            # Если блоков нет, возвращаем исходный текст
            logger.info("❌ JSON-блоки не найдены, возвращаем исходный текст")
            return hybrid_response, []
        
        # Очищаем исходный текст от всех JSON-блоков
        cleaned_text = hybrid_response
        for block in json_blocks:
            # Удаляем весь блок ``` ... ``` из текста
            cleaned_text = re.sub(r'```(?:json)?\s*' + re.escape(block) + r'\s*```', '', cleaned_text, flags=re.DOTALL)
        
        # Дополнительная очистка: удаляем лишние переносы строк
        cleaned_text = re.sub(r'\n\s*\n\s*\n', '\n\n', cleaned_text).strip()
        
        # Парсим все найденные JSON-блоки
        tool_calls = []
        for i, json_block in enumerate(json_blocks):
            logger.info(f"🔧 Обрабатываем блок {i+1}: {json_block[:100]}...")
            try:
                # Парсим JSON
                tool_call = json.loads(json_block.strip())
                logger.info(f"🔧 Распарсенный JSON: {tool_call}")
                
                # Проверяем формат JSON
                if isinstance(tool_call, dict):
                    # Формат 1: {"tool_calls": [...]}
                    if 'tool_calls' in tool_call:
                        tool_calls_list = tool_call.get('tool_calls', [])
                        logger.info(f"🔧 Найдено {len(tool_calls_list)} вызовов инструментов в массиве")
                        tool_calls.extend(tool_calls_list)
                    
                    # Формат 2: {"tool_name": "...", "parameters": {...}}
                    elif 'tool_name' in tool_call:
                        logger.info(f"🔧 Найден одиночный инструмент: {tool_call.get('tool_name')}")
                        tool_calls.append(tool_call)
                    else:
                        logger.warning(f"⚠️ JSON не содержит tool_calls или tool_name: {tool_call}")
                else:
                    logger.warning(f"⚠️ JSON не является словарем: {tool_call}")
                    
            except json.JSONDecodeError as e:
                logger.warning(f"⚠️ Не удалось распарсить JSON блок: {e}")
                continue
            except Exception as e:
                logger.error(f"❌ Ошибка обработки JSON блока: {e}")
                continue
        
        return cleaned_text, tool_calls

    async def process_user_message(self, user_id: int, text: str) -> str:
        """
        Обрабатывает сообщение пользователя с использованием двухэтапной архитектуры:
        1. Этап 1: Классификация стадии диалога
        2. Этап 2: Основной цикл "Мышления и Речи" с итеративным выполнением инструментов
        
        Args:
            user_id: ID пользователя Telegram
            text: Текст сообщения пользователя
            
        Returns:
            Сгенерированный ответ бота
        """
        # Логируем начало обработки диалога
        log_dialog_start(logger, user_id, text)
        
        # Получаем или создаем контекст для текущего пользователя
        session_context = self.session_contexts.setdefault(user_id, {})
        
        # Создаем трейсер для этого диалога
        tracer = DialogueTracer(user_id=user_id, user_message=text)
        
        # Максимальное количество итераций в цикле мышления
        MAX_ITERATIONS = 5
        
        try:
            # 0. Загружаем (или создаем) клиента
            client = self.client_repository.get_or_create_by_telegram_id(user_id)
            tracer.add_event("👤 Клиент загружен", f"ID клиента: {client.id}, Имя: {client.first_name}, Телефон: {client.phone_number}")
            
            # 1. Получаем историю диалога (окно контекста - последние N сообщений)
            history_records = self.repository.get_recent_messages(user_id, limit=self.CONTEXT_WINDOW_SIZE)
            tracer.add_event("📚 История диалога загружена", f"Количество сообщений: {len(history_records)} (окно контекста: {self.CONTEXT_WINDOW_SIZE})")
            
            # Преобразуем историю в расширенный формат для Gemini
            dialog_history: List[Dict] = []
            for record in history_records:
                role = "user" if record.role == "user" else "model"
                dialog_history.append({
                    "role": role,
                    "parts": [{"text": record.message_text}]
                })
            
            # 2. Сохраняем новое сообщение пользователя в БД
            self.repository.add_message(
                user_id=user_id,
                role="user",
                message_text=text
            )
            tracer.add_event("💾 Сообщение сохранено в БД", f"Роль: user, Текст: {text}")
            
            # --- ЭТАП 1: КЛАССИФИКАЦИЯ ---
            tracer.add_event("🔍 Этап 1: Классификация", "Определяем стадию диалога")
            logger.info("🔍 Этап 1: Классификация стадии диалога")
            
            # Формируем промпт для классификации
            classification_prompt = self.prompt_builder.build_classification_prompt(
                history=dialog_history,
                user_message=text
            )
            
            tracer.add_event("📝 Промпт классификации сформирован", {
                "prompt": classification_prompt,
                "length": len(classification_prompt)
            })
            
            # Создаем историю для первого вызова LLM
            classification_history = [
                {
                    "role": "user",
                    "parts": [{"text": classification_prompt}]
                }
            ]
            
            # Первый вызов LLM для классификации (без инструментов)
            stage_str = await self.llm_service.generate_response(classification_history, tracer=tracer)
            tracer.add_event("✅ Ответ классификации получен", f"Ответ: {stage_str}")
            logger.info(f"🔍 Сырой ответ классификации: '{stage_str}'")
            
            # Парсим стадию
            stage = self.parse_stage(stage_str)
            tracer.add_event("📊 Стадия определена", f"Стадия: {stage}")
            logger.info(f"🎯 Определена стадия: '{stage}'")
            
            # Быстрый путь для конфликтных ситуаций
            if stage == 'conflict_escalation':
                logger.warning(f"⚠️ КОНФЛИКТНАЯ СТАДИЯ: Немедленная эскалация на менеджера")
                
                tracer.add_event("⚠️ Конфликтная ситуация", "Эскалация на менеджера")
                
                # Вызываем менеджера с текстом сообщения пользователя как причиной
                manager_response = self.tool_service.call_manager(text)
                
                tracer.add_event("👨‍💼 Вызов менеджера", f"Ответ: {manager_response['response_to_user']}")
                logger.info(f"👨‍💼 Действие: эскалация на менеджера")
                
                # Сохраняем ответ бота в БД
                self.repository.add_message(
                    user_id=user_id,
                    role="model",
                    message_text=manager_response['response_to_user']
                )
                
                tracer.add_event("💾 Ответ менеджера сохранен", f"Текст: {manager_response['response_to_user']}")
                
                # Логируем завершение обработки
                log_dialog_end(logger, manager_response['response_to_user'])
                
                # Возвращаем ответ пользователю и завершаем обработку
                return manager_response['response_to_user']
            
            # --- ЭТАП 2: ОСНОВНОЙ ЦИКЛ "МЫШЛЕНИЯ И РЕЧИ" ---
            tracer.add_event("🧠 Этап 2: Основной цикл мышления", f"Максимум итераций: {MAX_ITERATIONS}")
            logger.info("🧠 Этап 2: Основной цикл мышления и речи")
            
            # Получаем данные стадии из новой структуры patterns
            stage_data = self.prompt_builder.dialogue_patterns.get(stage, {})
            stage_goal = stage_data.get('goal', 'Помочь клиенту')
            stage_scenario = stage_data.get('scenario', [])
            available_tools = stage_data.get('available_tools', [])
            
            tracer.add_event("📋 Данные стадии загружены", {
                "stage": stage,
                "goal": stage_goal,
                "scenario_steps": len(stage_scenario),
                "available_tools": available_tools
            })
            
            # Переменные для цикла мышления
            tool_results = ""
            bot_response_text = ""
            
            # Основной цикл мышления
            for iteration in range(MAX_ITERATIONS):
                tracer.add_event(f"🔄 Итерация {iteration + 1}", f"Цикл мышления")
                logger.info(f"🔄 Итерация {iteration + 1}/{MAX_ITERATIONS} цикла мышления")
                
                # Формируем промпт в зависимости от итерации
                if iteration == 0:
                    # Первая итерация - планирование (только сбор данных)
                    main_prompt = self.prompt_builder.build_planning_prompt(
                        stage_name=stage,
                        stage_scenario=stage_scenario,
                        available_tools=available_tools,
                        history=dialog_history,
                        user_message=text,
                        client_name=client.first_name,
                        client_phone_saved=bool(client.phone_number)
                    )
                else:
                    # Последующие итерации - синтез
                    main_prompt = self.prompt_builder.build_synthesis_prompt(
                        stage_name=stage,
                        stage_scenario=stage_scenario,
                        available_tools=available_tools,
                        history=dialog_history,
                        user_message=text,
                        tool_results=tool_results,
                        client_name=client.first_name,
                        client_phone_saved=bool(client.phone_number)
                    )
                
                tracer.add_event(f"📝 Промпт мышления {iteration + 1} сформирован", {
                    "prompt_length": len(main_prompt),
                    "tool_results_length": len(tool_results),
                    "stage": stage
                })
                
                # Создаем историю для вызова LLM
                main_history = [
                    {
                        "role": "user",
                        "parts": [{"text": main_prompt}]
                    }
                ]
                
                # Вызов LLM с инструментами, доступными для текущей стадии
                from app.services.tool_definitions import all_tools_dict
                
                # Фильтруем инструменты по доступным для стадии
                stage_tools = []
                if available_tools:
                    for tool_name in available_tools:
                        if tool_name in all_tools_dict:
                            stage_tools.append(all_tools_dict[tool_name])
                
                tracer.add_event(f"🔧 Инструменты для стадии {iteration + 1}", {
                    "available_tools": available_tools,
                    "filtered_tools_count": len(stage_tools),
                    "tool_names": [tool.name for tool in stage_tools]
                })
                
                main_response = await self.llm_service.generate_response(main_history, stage_tools, tracer=tracer)
                
                tracer.add_event(f"✅ Ответ мышления {iteration + 1} получен", {
                    "response_length": len(main_response),
                    "iteration": iteration + 1
                })
                logger.info(f"✅ Ответ мышления {iteration + 1} получен")
                
                # Парсим гибридный ответ (JSON + текст)
                tracer.add_event(f"🔍 Парсинг ответа {iteration + 1}", f"Длина ответа: {len(main_response)}")
                logger.info(f"🔍 Парсинг ответа мышления {iteration + 1}")
                
                cleaned_text, tool_calls = self.parse_hybrid_response(main_response)
                
                # Анализируем ответ и принимаем решение
                if tool_calls:
                    # Есть вызовы инструментов - выполняем их
                    tracer.add_event(f"⚙️ Выполнение инструментов {iteration + 1}", {
                        "tool_calls": tool_calls,
                        "tool_calls_count": len(tool_calls),
                        "cleaned_text_length": len(cleaned_text)
                    })
                    logger.info(f"⚙️ Выполнение {len(tool_calls)} инструментов в итерации {iteration + 1}")
                    
                    # Выполняем инструменты
                    iteration_results = []
                    for tool_call in tool_calls:
                        tool_name = tool_call.get('tool_name')
                        parameters = tool_call.get('parameters', {})
                        
                        # Добавляем user_telegram_id к параметрам для инструментов, которые его требуют
                        if tool_name in ['cancel_appointment_by_id', 'reschedule_appointment_by_id']:
                            parameters['user_telegram_id'] = user_id
                        
                        tracer.add_event(f"🔧 Выполнение инструмента {iteration + 1}", f"Инструмент: {tool_name}, Параметры: {parameters}")
                        
                        try:
                            # Выполняем инструмент через ToolOrchestratorService
                            tool_result = await self.tool_orchestrator.execute_single_tool(tool_name, parameters, user_id)
                            iteration_results.append(f"Результат {tool_name}: {tool_result}")
                            
                            # Специальная трассировка для операций с записями
                            if tool_name == 'get_my_appointments':
                                # Получаем структурированные данные напрямую из AppointmentService
                                appointments_data = self.appointment_service.get_my_appointments(user_id)
                                session_context['appointments_in_focus'] = appointments_data
                                logger.info(f"🔍 Записи сохранены в память: {appointments_data}")
                                tracer.add_event("🔍 Записи сохранены в память", {
                                    "appointments_count": len(appointments_data),
                                    "appointments": appointments_data
                                })
                            
                            tracer.add_event(f"✅ Инструмент {iteration + 1} выполнен", f"Инструмент: {tool_name}, Результат: {tool_result}")
                            logger.info(f"✅ Инструмент выполнен в итерации {iteration + 1}: {tool_name}")
                            
                        except Exception as e:
                            error_msg = f"Ошибка выполнения {tool_name}: {str(e)}"
                            iteration_results.append(error_msg)
                            tracer.add_event(f"❌ Ошибка инструмента {iteration + 1}", f"Инструмент: {tool_name}, Ошибка: {str(e)}")
                            logger.error(f"❌ Ошибка выполнения инструмента {tool_name} в итерации {iteration + 1}: {e}")
                    
                    # Обновляем результаты инструментов для следующей итерации
                    if iteration_results:
                        tool_results += f"\n--- Итерация {iteration + 1} ---\n" + "\n".join(iteration_results) + "\n"
                    
                    # КЛЮЧЕВОЕ ИЗМЕНЕНИЕ: Игнорируем текст на первой итерации (сбор данных)
                    if iteration == 0:  # Первая итерация (iteration + 1 = 1)
                        tracer.add_event(f"🚫 Игнорирование текста на первой итерации {iteration + 1}", {
                            "ignored_text": cleaned_text.strip(),
                            "reason": "Первая итерация предназначена только для сбора данных"
                        })
                        logger.info(f"🚫 Игнорируем текст на первой итерации {iteration + 1} - только сбор данных")
                    elif cleaned_text.strip():
                        # На второй и последующих итерациях сохраняем текст для финального ответа
                        bot_response_text = cleaned_text.strip()
                        tracer.add_event(f"📝 Текст сохранен для финального ответа {iteration + 1}", {
                            "text": bot_response_text,
                            "length": len(bot_response_text)
                        })
                        logger.info(f"📝 Текст сохранен для финального ответа в итерации {iteration + 1}")
                    
                    # Продолжаем цикл для следующей итерации
                    continue
                    
                elif cleaned_text.strip():
                    # Нет инструментов, но есть текстовый ответ - это финальный ответ
                    bot_response_text = cleaned_text.strip()
                    tracer.add_event(f"✅ Финальный ответ получен в итерации {iteration + 1}", {
                        "response": bot_response_text,
                        "length": len(bot_response_text),
                        "iteration": iteration + 1
                    })
                    logger.info(f"✅ Финальный ответ получен в итерации {iteration + 1}")
                    break
                    
                else:
                    # Нет ни инструментов, ни текста - странная ситуация
                    tracer.add_event(f"⚠️ Пустой ответ в итерации {iteration + 1}", "Нет инструментов и текста")
                    logger.warning(f"⚠️ Пустой ответ в итерации {iteration + 1}")
                    break
            
            # Если цикл завершился без финального ответа, генерируем fallback
            if not bot_response_text.strip():
                tracer.add_event("⚠️ Fallback ответ", "Цикл завершился без финального ответа")
                logger.warning("⚠️ Цикл мышления завершился без финального ответа, генерируем fallback")
                
                fallback_prompt = f"Клиент написал: '{text}'. Сформулируй вежливый ответ, что ты понял его запрос и готов помочь."
                fallback_history = [
                    {
                        "role": "user",
                        "parts": [{"text": fallback_prompt}]
                    }
                ]
                
                bot_response_text = await self.llm_service.generate_response(fallback_history, tracer=tracer)
                tracer.add_event("✅ Fallback ответ получен", {
                    "response": bot_response_text,
                    "length": len(bot_response_text)
                })
                logger.info("✅ Fallback ответ сгенерирован")
            
            # Сохраняем финальный ответ бота в БД
            self.repository.add_message(
                user_id=user_id,
                role="model",
                message_text=bot_response_text
            )
            
            tracer.add_event("💾 Финальный ответ сохранен", {
                "text": bot_response_text,
                "length": len(bot_response_text)
            })
            
            # Логируем завершение обработки
            log_dialog_end(logger, bot_response_text)
            
            # Возвращаем сгенерированный текст
            return bot_response_text
            
        except Exception as e:
            tracer.add_event("❌ Ошибка обработки", f"Ошибка: {str(e)}")
            log_error(logger, e, f"Обработка сообщения от user_id={user_id}")
            raise
        finally:
            # Сохраняем трассировку в любом случае
            tracer.save_trace()
    

    def clear_history(self, user_id: int) -> int:
        """
        Очищает всю историю диалога для пользователя.
        
        Args:
            user_id: ID пользователя Telegram
            
        Returns:
            Количество удаленных записей
        """
        return self.repository.clear_user_history(user_id)