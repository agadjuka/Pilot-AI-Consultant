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
    Реализует двухэтапную архитектуру: Планирование (read_only_tools) -> Синтез (write_tools).
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
    

    async def process_user_message(self, user_id: int, text: str) -> str:
        """
        Обрабатывает сообщение пользователя с использованием двухэтапной архитектуры:
        1. Этап 1: Планирование инструментов (только read_only_tools)
        2. Этап 2: Синтез финального ответа (может вернуть текст или JSON с write_tools)
        3. Если вернулся JSON - выполняем исполнительный инструмент и делаем финальный вызов
        
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
            
            # ЭТАП 1: Планирование
            tracer.add_event("🔍 Этап 1: Планирование", "Начинаем первый вызов LLM")
            logger.info("🔍 Этап 1: Планирование")
            
            # Формируем скрытый контекст ДО планирования
            hidden_context = ""
            
            # Проверяем, есть ли записи в памяти для формирования скрытого контекста
            if 'appointments_in_focus' in session_context:
                appointments_data = session_context.get('appointments_in_focus', [])
                if appointments_data:
                    hidden_context = "# СКРЫТЫЙ КОНТЕКСТ ЗАПИСЕЙ (ИСПОЛЬЗУЙ ДЛЯ ИЗВЛЕЧЕНИЯ ID):\n" + json.dumps(appointments_data, ensure_ascii=False)
                    tracer.add_event("🔍 Скрытый контекст сформирован ДО планирования", {
                        "appointments_count": len(appointments_data),
                        "context": hidden_context
                    })
            
            # Формируем промпт для планирования
            planning_prompt = self.prompt_builder.build_planning_prompt(
                history=dialog_history,
                user_message=text,
                hidden_context=hidden_context
            )
            
            tracer.add_event("📝 Промпт планирования сформирован", {
                "prompt": planning_prompt,
                "length": len(planning_prompt)
            })
            
            # Создаем историю для первого вызова LLM
            planning_history = [
                {
                    "role": "user",
                    "parts": [{"text": planning_prompt}]
                }
            ]
            
            # Первый вызов LLM для планирования (только read_only_tools)
            from app.services.tool_definitions import read_only_tools_obj
            planning_response = await self.llm_service.generate_response(planning_history, read_only_tools_obj)
            tracer.add_event("✅ Ответ планирования получен", f"Ответ: {planning_response}")
            logger.info(f"🔍 Сырой ответ LLM: '{planning_response}'")
            
            # Парсим JSON-ответ с инструментами
            tool_calls = []
            stage = 'fallback'  # Стадия по умолчанию
            try:
                # Удаляем markdown блоки если они есть
                cleaned_response = planning_response.strip()
                if cleaned_response.startswith('```') and cleaned_response.endswith('```'):
                    cleaned_response = cleaned_response[3:-3].strip()
                elif cleaned_response.startswith('```json'):
                    cleaned_response = cleaned_response[7:-3].strip()
                
                parsed_response = json.loads(cleaned_response)
                
                # Проверяем формат ответа
                if isinstance(parsed_response, dict):
                    # Новый формат: {"stage": "...", "tool_calls": [...]}
                    stage = parsed_response.get('stage', 'fallback')
                    tool_calls = parsed_response.get('tool_calls', [])
                elif isinstance(parsed_response, list):
                    # Старый формат: [{"tool_name": "...", "parameters": {...}}]
                    tool_calls = parsed_response
                    stage = 'fallback'  # Для старого формата используем fallback
                
                tracer.add_event("📊 Результат парсинга", {
                    "stage": stage,
                    "tool_calls": tool_calls,
                    "tool_calls_count": len(tool_calls),
                    "tool_calls_types": [type(tc).__name__ for tc in tool_calls] if tool_calls else []
                })
                logger.info(f"🎯 Определена стадия: '{stage}', запланировано инструментов: {len(tool_calls)}")
                logger.info(f"🔍 Типы элементов tool_calls: {[type(tc).__name__ for tc in tool_calls] if tool_calls else 'пусто'}")
                
            except json.JSONDecodeError as e:
                logger.error(f"❌ Ошибка парсинга JSON ответа планирования: {e}")
                logger.error(f"❌ Сырой ответ: '{planning_response}'")
                tracer.add_event("❌ Ошибка парсинга JSON", f"Ошибка: {str(e)}")
                # Fallback: пустой список инструментов
                tool_calls = []
                stage = 'fallback'
            
            # Выполнение инструментов (если они запланированы)
            tool_results = ""
            if tool_calls:
                tracer.add_event("⚙️ Выполнение инструментов", f"Количество инструментов: {len(tool_calls)}")
                logger.info(f"⚙️ Выполнение {len(tool_calls)} инструментов")
                
                # Выполняем каждый инструмент
                for tool_call in tool_calls:
                    # Проверяем формат tool_call
                    if isinstance(tool_call, str):
                        logger.warning(f"⚠️ Получена строка вместо объекта инструмента: '{tool_call}'")
                        tracer.add_event("⚠️ Неверный формат инструмента", f"Получена строка: {tool_call}")
                        continue
                    
                    if not isinstance(tool_call, dict):
                        logger.warning(f"⚠️ Неверный тип инструмента: {type(tool_call)}, значение: {tool_call}")
                        tracer.add_event("⚠️ Неверный тип инструмента", f"Тип: {type(tool_call)}, Значение: {tool_call}")
                        continue
                    
                    tool_name = tool_call.get('tool_name')
                    parameters = tool_call.get('parameters', {})
                    
                    if not tool_name:
                        logger.warning(f"⚠️ Отсутствует tool_name в инструменте: {tool_call}")
                        tracer.add_event("⚠️ Отсутствует tool_name", f"Инструмент: {tool_call}")
                        continue
                    
                    tracer.add_event(f"🔧 Выполнение инструмента", f"Инструмент: {tool_name}, Параметры: {parameters}")
                    
                    try:
                        # Вызываем инструмент через ToolService
                        result = await self.tool_service.execute_tool(tool_name, parameters, user_id)
                        tool_results += f"Результат {tool_name}: {result}\n"
                        
                        # Сохраняем результат в память, если это get_my_appointments
                        if tool_name == 'get_my_appointments':
                            # Получаем структурированные данные напрямую из AppointmentService
                            appointments_data = self.appointment_service.get_my_appointments(user_id)
                            session_context['appointments_in_focus'] = appointments_data
                            logger.info(f"🔍 Записи сохранены в память: {appointments_data}")
                            tracer.add_event("🔍 Записи сохранены в память", {
                                "appointments_count": len(appointments_data),
                                "appointments": appointments_data
                            })
                        
                        tracer.add_event(f"✅ Инструмент выполнен", f"Инструмент: {tool_name}, Результат: {result}")
                        
                    except Exception as e:
                        error_msg = f"Ошибка выполнения {tool_name}: {str(e)}"
                        tool_results += error_msg + "\n"
                        tracer.add_event(f"❌ Ошибка инструмента", f"Инструмент: {tool_name}, Ошибка: {str(e)}")
                        logger.error(f"❌ Ошибка выполнения инструмента {tool_name}: {e}")
            else:
                tracer.add_event("ℹ️ Инструменты не требуются", "Пустой список инструментов")
                logger.info("ℹ️ Инструменты не требуются")
            
            # Логика скрытого контекста: получаем записи если их нет в памяти для стадий отмены/переноса
            if stage in ['cancellation_request', 'rescheduling']:
                # Если нет записей в памяти, получаем их
                if 'appointments_in_focus' not in session_context:
                    appointments_data = self.appointment_service.get_my_appointments(user_id)
                    session_context['appointments_in_focus'] = appointments_data
                    logger.info(f"🔍 Записи получены и сохранены в память: {appointments_data}")
                    tracer.add_event("🔍 Записи получены и сохранены в память", {
                        "appointments_count": len(appointments_data),
                        "appointments": appointments_data
                    })
                
                # Обновляем скрытый контекст с актуальными данными
                appointments_data = session_context.get('appointments_in_focus', [])
                if appointments_data:
                    hidden_context = "# СКРЫТЫЙ КОНТЕКСТ ЗАПИСЕЙ (ИСПОЛЬЗУЙ ДЛЯ ИЗВЛЕЧЕНИЯ ID):\n" + json.dumps(appointments_data, ensure_ascii=False)
                    tracer.add_event("🔍 Скрытый контекст обновлен", {
                        "stage": stage,
                        "appointments_count": len(appointments_data),
                        "context": hidden_context
                    })
            
            # Логика очистки памяти: очищаем память о записях, если сменили тему
            if stage not in ['appointment_cancellation', 'rescheduling', 'view_booking', 'cancellation_request']:
                if 'appointments_in_focus' in session_context:
                    del session_context['appointments_in_focus']  # Очищаем, если сменили тему
            
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
            
            # ЭТАП 2: Синтез финального ответа
            tracer.add_event("🎨 Этап 2: Синтез ответа", "Начинаем второй вызов LLM")
            logger.info("🎨 Этап 2: Синтез финального ответа")
            
            # Добавляем скрытый контекст к результатам инструментов для этапа синтеза
            if hidden_context:
                tool_results += "\n" + hidden_context
                tracer.add_event("🔍 Скрытый контекст добавлен к результатам", {
                    "stage": stage,
                    "context": hidden_context
                })
            
            # Формируем промпт для синтеза
            synthesis_prompt = self.prompt_builder.build_synthesis_prompt(
                history=dialog_history,
                user_message=text,
                tool_results=tool_results,
                stage=stage,
                client_name=client.first_name,
                client_phone_saved=bool(client.phone_number)
            )
            
            tracer.add_event("📝 Промпт синтеза сформирован", {
                "prompt": synthesis_prompt,
                "length": len(synthesis_prompt),
                "stage": stage
            })
            
            # Создаем историю для второго вызова LLM
            synthesis_history = [
                {
                    "role": "user",
                    "parts": [{"text": synthesis_prompt}]
                }
            ]
            
            # Второй вызов LLM для синтеза финального ответа (с write_tools)
            from app.services.tool_definitions import write_tools_obj
            synthesis_response = await self.llm_service.generate_response(synthesis_history, write_tools_obj)
            
            tracer.add_event("✅ Ответ синтеза получен", {
                "response": synthesis_response,
                "length": len(synthesis_response)
            })
            logger.info("✅ Ответ синтеза получен")
            
            # Используем парсер гибридных ответов для обработки ответа синтеза
            tracer.add_event("🔍 Парсинг гибридного ответа", f"Длина ответа: {len(synthesis_response)}")
            logger.info("🔍 Парсинг гибридного ответа синтеза")
            
            # Парсим гибридный ответ (JSON + текст)
            cleaned_text, tool_execution_results = await self._parse_hybrid_response(synthesis_response, user_id)
            
            if tool_execution_results:
                # Если были выполнены инструменты, логируем это
                tracer.add_event("⚙️ Инструменты выполнены из гибридного ответа", {
                    "results": tool_execution_results,
                    "cleaned_text_length": len(cleaned_text)
                })
                logger.info("⚙️ Инструменты выполнены из гибридного ответа")
                
                # Если есть результат выполнения инструментов, делаем финальный вызов для сообщения об успехе
                final_prompt = f"Инструменты выполнены успешно. Результаты: {tool_execution_results}. Сформулируй краткое сообщение пользователю об успешном выполнении действия."
                
                final_history = [
                    {
                        "role": "user",
                        "parts": [{"text": final_prompt}]
                    }
                ]
                
                bot_response_text = await self.llm_service.generate_response(final_history)
                tracer.add_event("✅ Финальный ответ получен после выполнения инструментов", {
                    "response": bot_response_text,
                    "length": len(bot_response_text)
                })
                logger.info("✅ Финальный ответ сгенерирован после выполнения инструментов")
            else:
                # Это обычный текстовый ответ (возможно, очищенный от JSON-блоков)
                bot_response_text = cleaned_text
                tracer.add_event("📝 Использован очищенный текстовый ответ", {
                    "response": bot_response_text,
                    "length": len(bot_response_text)
                })
                logger.info("📝 Использован очищенный текстовый ответ")
            
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
    
    async def _parse_hybrid_response(self, raw_response: str, user_id: int) -> tuple[str, str]:
        """
        Парсит гибридный ответ LLM (JSON + текст) и выполняет инструменты.
        
        Args:
            raw_response: Сырой ответ от LLM
            user_id: ID пользователя для выполнения инструментов
            
        Returns:
            Кортеж (очищенный_текст_для_пользователя, результат_выполнения_инструментов)
        """
        import re
        import json
        
        # Ищем все блоки ```json ... ``` в ответе
        json_blocks = re.findall(r'```json\s*([\s\S]*?)\s*```', raw_response)
        
        if not json_blocks:
            # Если блоков нет, возвращаем исходный текст
            return raw_response, ""
        
        # Очищаем исходный текст от всех JSON-блоков
        cleaned_text = raw_response
        for block in json_blocks:
            # Удаляем весь блок ```json ... ``` из текста
            cleaned_text = re.sub(r'```json\s*' + re.escape(block) + r'\s*```', '', cleaned_text, flags=re.DOTALL)
        
        # Дополнительная очистка: удаляем лишние переносы строк
        cleaned_text = re.sub(r'\n\s*\n\s*\n', '\n\n', cleaned_text).strip()
        
        # Выполняем все найденные инструменты
        tool_results = []
        for json_block in json_blocks:
            try:
                # Парсим JSON
                tool_call = json.loads(json_block.strip())
                
                # Проверяем, что это вызов инструмента
                if isinstance(tool_call, dict) and 'tool_name' in tool_call:
                    tool_name = tool_call.get('tool_name')
                    parameters = tool_call.get('parameters', {})
                    
                    # Добавляем user_telegram_id к параметрам для инструментов, которые его требуют
                    if tool_name in ['cancel_appointment_by_id', 'reschedule_appointment_by_id']:
                        parameters['user_telegram_id'] = user_id
                    
                    logger.info(f"🔧 Выполнение инструмента из гибридного ответа: {tool_name}")
                    
                    # Выполняем инструмент через ToolOrchestratorService
                    tool_result = await self.tool_orchestrator.execute_single_tool(tool_name, parameters, user_id)
                    
                    tool_results.append(f"Результат {tool_name}: {tool_result}")
                    logger.info(f"✅ Инструмент выполнен: {tool_name}")
                    
            except json.JSONDecodeError as e:
                logger.warning(f"⚠️ Не удалось распарсить JSON блок: {e}")
                continue
            except Exception as e:
                logger.error(f"❌ Ошибка выполнения инструмента: {e}")
                tool_results.append(f"Ошибка выполнения инструмента: {str(e)}")
        
        # Объединяем результаты инструментов
        combined_results = "\n".join(tool_results) if tool_results else ""
        
        return cleaned_text, combined_results

    def clear_history(self, user_id: int) -> int:
        """
        Очищает всю историю диалога для пользователя.
        
        Args:
            user_id: ID пользователя Telegram
            
        Returns:
            Количество удаленных записей
        """
        return self.repository.clear_user_history(user_id)