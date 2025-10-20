from typing import List, Dict
import asyncio
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
from app.repositories.master_schedule_repository import MasterScheduleRepository
from app.services.llm_service import get_llm_service
from app.services.appointment_service import AppointmentService
from app.services.tool_service import ToolService
from app.services.db_calendar_service import DBCalendarService
from app.services.prompt_builder_service import PromptBuilderService
from app.core.dialogue_pattern_loader import dialogue_patterns
from app.services.dialogue_tracer_service import DialogueTracer
from app.core.logging_config import log_dialog_start, log_dialog_end, log_error
from app.services.tool_definitions import all_tools_dict

# Получаем логгер для этого модуля
logger = logging.getLogger(__name__)


class DialogService:
    """
    Оркестратор диалоговой логики.
    Координирует работу между хранилищем истории диалогов и AI-моделью.
    Реализует финальную трехэтапную архитектуру: Классификация -> Мышление -> Синтез.
    """
    
    # Размер окна контекста - последние N сообщений
    CONTEXT_WINDOW_SIZE = 12
    
    def __init__(self):
        """
        Инициализирует сервис диалога.
        """
        self.repository = DialogHistoryRepository()
        self.llm_service = get_llm_service()
        
        # Инициализируем PromptBuilderService
        self.prompt_builder = PromptBuilderService()
        
        # Инициализируем репозитории для ToolService
        self.service_repository = ServiceRepository()
        self.master_repository = MasterRepository()
        self.appointment_repository = AppointmentRepository()
        self.client_repository = ClientRepository()
        
        # Инициализируем DB Calendar Service
        self.master_schedule_repository = MasterScheduleRepository()
        self.db_calendar_service = DBCalendarService(
            appointment_repository=self.appointment_repository,
            master_repository=self.master_repository,
            master_schedule_repository=self.master_schedule_repository
        )
        
        # Создаем экземпляр AppointmentService
        self.appointment_service = AppointmentService(
            appointment_repository=self.appointment_repository,
            client_repository=self.client_repository,
            master_repository=self.master_repository,
            service_repository=self.service_repository,
            db_calendar_service=self.db_calendar_service
        )
        
        # Создаем экземпляр ToolService
        self.tool_service = ToolService(
            service_repository=self.service_repository,
            master_repository=self.master_repository,
            appointment_service=self.appointment_service,
            db_calendar_service=self.db_calendar_service,
            client_repository=self.client_repository
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
        
        # Менеджер контекста для отслеживания ключевых сущностей диалога
        # Формат: {user_telegram_id: {"service_name": str, "date": str, "master_name": str, ...}}
        self.dialog_contexts = {}

    def _decode_string_field(self, field_value):
        """
        Декодирует байтовую строку в обычную строку, если необходимо.
        
        Args:
            field_value: Значение поля из базы данных
            
        Returns:
            Декодированная строка или исходное значение
        """
        if isinstance(field_value, bytes):
            return field_value.decode('utf-8')
        return field_value
    
    def _get_filtered_tools(self, available_tools: List[str]):
        """
        Фильтрует инструменты по списку доступных для текущей стадии.
        
        Args:
            available_tools: Список имен доступных инструментов
            
        Returns:
            Список отфильтрованных FunctionDeclaration объектов
        """
        if not available_tools:
            return []
        
        filtered_tools = []
        for tool_name in available_tools:
            if tool_name in all_tools_dict:
                filtered_tools.append(all_tools_dict[tool_name])
        
        return filtered_tools
    

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
    
    def extract_and_save_entities(self, tool_calls: List[Dict], user_message: str, dialog_context: Dict, tracer=None) -> None:
        """
        Извлекает ключевые сущности из параметров инструментов и исходного сообщения пользователя
        и сохраняет их в контексте диалога.
        
        Args:
            tool_calls: Список вызовов инструментов
            user_message: Исходное сообщение пользователя
            dialog_context: Контекст диалога для обновления
        """
        # Анализируем параметры в tool_calls
        extracted_entities = {}
        
        for tool_call in tool_calls:
            params = tool_call.get('parameters', {})
            
            # Сохраняем service_name если есть
            if 'service_name' in params and params['service_name']:
                dialog_context['service_name'] = params['service_name']
                extracted_entities['service_name'] = params['service_name']
                logger.info(f"🔍 Сохранен service_name в контекст: {params['service_name']}")
            
            # Сохраняем date если есть
            if 'date' in params and params['date']:
                dialog_context['date'] = params['date']
                extracted_entities['date'] = params['date']
                logger.info(f"🔍 Сохранена date в контекст: {params['date']}")
            
            # Сохраняем master_name если есть
            if 'master_name' in params and params['master_name']:
                dialog_context['master_name'] = params['master_name']
                extracted_entities['master_name'] = params['master_name']
                logger.info(f"🔍 Сохранен master_name в контекст: {params['master_name']}")
        
        # Логируем извлеченные сущности в трассировку
        if tracer and extracted_entities:
            tracer.add_event("🔍 Извлечение сущностей из tool_calls", {
                "extracted_entities": extracted_entities,
                "tool_calls_count": len(tool_calls),
                "updated_context": dialog_context
            })
        
        # Дополнительно анализируем исходное сообщение пользователя для извлечения сущностей
        # Это поможет "вспомнить" информацию, которую пользователь упоминал ранее
        user_message_lower = user_message.lower()
        
        # Простое извлечение дат из сообщения (можно расширить)
        import re
        date_patterns = [
            r'\d{1,2}[./]\d{1,2}[./]\d{2,4}',  # 15.01.2024 или 15/01/24
            r'\d{1,2}\s+(января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)',  # 15 января
            r'(сегодня|завтра|послезавтра)',  # относительные даты
        ]
        
        extracted_from_message = {}
        for pattern in date_patterns:
            match = re.search(pattern, user_message_lower)
            if match and 'date' not in dialog_context:
                dialog_context['date'] = match.group(0)
                extracted_from_message['date'] = match.group(0)
                logger.info(f"🔍 Извлечена дата из сообщения: {match.group(0)}")
                break
        
        # Логируем извлечение из сообщения пользователя в трассировку
        if tracer and extracted_from_message:
            tracer.add_event("🔍 Извлечение сущностей из сообщения пользователя", {
                "extracted_from_message": extracted_from_message,
                "user_message": user_message,
                "updated_context": dialog_context
            })
    
    def _parse_parameters_string(self, params_string: str) -> Dict[str, str]:
        """
        Парсит строку параметров в формате param1="value1", param2=value2 в словарь.
        
        Args:
            params_string: Строка с параметрами (например: 'date="2025-10-16", service_name="маникюр"')
            
        Returns:
            Словарь параметров {"param1": "value1", "param2": "value2"}
        """
        params = {}
        if not params_string.strip():
            return params
        
        # Регулярное выражение для поиска пар ключ="значение" или ключ=значение
        # Поддерживает русские символы и пробелы внутри значений
        param_pattern = r'(\w+)\s*=\s*("([^"]*)"|([^,\s]+))'
        matches = re.finditer(param_pattern, params_string)
        
        for match in matches:
            param_name = match.group(1)
            # Группа 3 - значение в кавычках, группа 4 - значение без кавычек
            param_value = match.group(3) if match.group(3) is not None else match.group(4)
            params[param_name] = param_value
        
        return params

    def _convert_parameter_types(self, parameters: Dict[str, str]) -> Dict[str, any]:
        """
        Преобразует типы параметров в соответствии с ожидаемыми типами инструментов.
        
        Args:
            parameters: Словарь параметров со строковыми значениями
            
        Returns:
            Словарь с правильно типизированными параметрами
        """
        converted_params = {}
        
        for key, value in parameters.items():
            if key in ['appointment_id', 'id']:
                # appointment_id должен быть integer (поддерживаем и 'id' для совместимости)
                try:
                    converted_params['appointment_id'] = int(value)
                except (ValueError, TypeError):
                    # Если не удается преобразовать, оставляем как есть для обработки ошибки
                    converted_params['appointment_id'] = value
            elif key in ['master_id', 'service_id', 'user_telegram_id']:
                # ID должны быть integer
                try:
                    converted_params[key] = int(value)
                except (ValueError, TypeError):
                    converted_params[key] = value
            elif key in ['new_time']:
                # Время должно быть строкой, но убедимся что формат правильный
                # Убираем лишние пробелы и кавычки
                cleaned_time = str(value).strip().strip('"\'')
                converted_params[key] = cleaned_time
            elif key in ['new_date', 'date']:
                # Дата должна быть строкой в формате YYYY-MM-DD
                cleaned_date = str(value).strip().strip('"\'')
                converted_params[key] = cleaned_date
            elif key in ['service_name', 'master_name', 'client_name']:
                # Имена должны быть строками, убираем кавычки
                cleaned_name = str(value).strip().strip('"\'')
                converted_params[key] = cleaned_name
            else:
                # Для остальных параметров просто убираем кавычки
                if isinstance(value, str):
                    cleaned_value = value.strip().strip('"\'')
                    converted_params[key] = cleaned_value
                else:
                    converted_params[key] = value
        
        return converted_params

    def parse_tool_calls_from_response(self, response: str) -> List[Dict]:
        """
        Парсит ответ LLM и извлекает вызовы инструментов в новом строковом формате.
        
        Args:
            response: Сырой ответ от LLM
            
        Returns:
            Список вызовов инструментов в формате [{"tool_name": "...", "parameters": {...}}]
        """
        tool_calls = []
        
        # Регулярное выражение для поиска строк TOOL_CALL: function_name(param="value")
        tool_call_pattern = r'TOOL_CALL:\s*(\w+)\((.*?)\)'
        matches = re.finditer(tool_call_pattern, response, re.MULTILINE | re.DOTALL)
        
        for match in matches:
            function_name = match.group(1)
            raw_params = match.group(2).strip()
            
            # Парсим параметры
            params = self._parse_parameters_string(raw_params)
            
            tool_call = {
                "tool_name": function_name,
                "parameters": params
            }
            tool_calls.append(tool_call)
            
            logger.info(f"🔧 [String Parser] Найден вызов: {function_name}({params})")
        
        return tool_calls

    def parse_tool_calls(self, planning_response_json: str) -> List[Dict]:
        """
        Парсит ответ от LLM и извлекает вызовы инструментов в новом строковом формате.
        
        Args:
            planning_response_json: Ответ от LLM (может содержать TOOL_CALL: или JSON)
            
        Returns:
            Список вызовов инструментов в формате [{"tool_name": "...", "parameters": {...}}]
        """
        # Сначала пробуем новый строковый формат
        tool_calls = self.parse_tool_calls_from_response(planning_response_json)
        
        if tool_calls:
            logger.info(f"🔧 [String Parser] Найдено {len(tool_calls)} вызовов в строковом формате")
            return tool_calls
        
        # Если строковый формат не найден, пробуем старый JSON (для обратной совместимости)
        logger.info("🔧 [Fallback] Пробуем JSON-парсинг")
        try:
            # Улучшенная очистка markdown-блоков
            cleaned_response = planning_response_json.strip()
            
            # Удаляем блоки ```json ... ``` или ``` ... ```
            if cleaned_response.startswith('```'):
                # Находим конец блока
                end_pos = cleaned_response.rfind('```')
                if end_pos > 0:
                    # Извлекаем содержимое между блоками
                    content = cleaned_response[3:end_pos].strip()
                    # Убираем префикс "json" если есть
                    if content.startswith('json'):
                        content = content[4:].strip()
                    cleaned_response = content
            
            parsed_response = json.loads(cleaned_response)
            
            # Проверяем формат ответа
            if isinstance(parsed_response, dict) and 'tool_calls' in parsed_response:
                return parsed_response.get('tool_calls', [])
            elif isinstance(parsed_response, list):
                # Старый формат: [{"tool_name": "...", "parameters": {...}}]
                return parsed_response
            
            logger.warning(f"⚠️ Неожиданный формат JSON ответа: {parsed_response}")
            return []
            
        except json.JSONDecodeError as e:
            logger.error(f"❌ Ошибка парсинга JSON ответа: {e}")
            logger.error(f"❌ Сырой ответ: '{planning_response_json}'")
            return []
    
    def parse_string_format_response(self, response: str) -> tuple[str, List[Dict]]:
        """
        Парсит ответ LLM в новом строковом формате TOOL_CALL: function_name(param="value").
        
        Args:
            response: Сырой ответ от LLM
            
        Returns:
            Кортеж (очищенный_текст_для_пользователя, список_вызовов_инструментов)
        """
        import re
        
        # Используем новый парсер для извлечения вызовов инструментов
        tool_calls = self.parse_tool_calls_from_response(response)
        
        if not tool_calls:
            # Если вызовов нет, возвращаем исходный текст с очисткой апострофов
            cleaned_text = response.strip('`')
            logger.info("❌ Строковые вызовы TOOL_CALL не найдены, возвращаем исходный текст с очисткой апострофов")
            return cleaned_text, []
        
        # Очищаем исходный текст от всех строк TOOL_CALL:
        cleaned_text = response
        # Удаляем строки с TOOL_CALL, включая обратные кавычки
        tool_call_pattern = r'`?TOOL_CALL:\s*(\w+)\((.*?)\)`?'
        cleaned_text = re.sub(tool_call_pattern, '', cleaned_text, flags=re.MULTILINE)
        
        # Дополнительная очистка: удаляем лишние переносы строк
        cleaned_text = re.sub(r'\n\s*\n\s*\n', '\n\n', cleaned_text).strip()
        
        # Убираем апострофы в начале и конце строки
        cleaned_text = cleaned_text.strip('`')
        
        logger.info(f"🔧 [String Format] Найдено {len(tool_calls)} вызовов, очищенный текст: {len(cleaned_text)} символов")
        
        return cleaned_text, tool_calls

    def parse_hybrid_response(self, hybrid_response: str) -> tuple[str, List[Dict]]:
        """
        Парсит гибридный ответ LLM (строковый формат + текст) и извлекает вызовы инструментов.
        
        Args:
            hybrid_response: Сырой ответ от LLM
            
        Returns:
            Кортеж (очищенный_текст_для_пользователя, список_вызовов_инструментов)
        """
        # Сначала пробуем новый строковый формат
        tool_calls = self.parse_tool_calls_from_response(hybrid_response)
        
        if tool_calls:
            # Очищаем исходный текст от всех строк TOOL_CALL:
            cleaned_text = hybrid_response
            # Удаляем строки с TOOL_CALL, включая обратные кавычки
            tool_call_pattern = r'`?TOOL_CALL:\s*(\w+)\((.*?)\)`?'
            cleaned_text = re.sub(tool_call_pattern, '', cleaned_text, flags=re.MULTILINE)
            
            # Дополнительная очистка: удаляем лишние переносы строк
            cleaned_text = re.sub(r'\n\s*\n\s*\n', '\n\n', cleaned_text).strip()
            
            # Убираем апострофы в начале и конце строки
            cleaned_text = cleaned_text.strip('`')
            
            logger.info(f"🔧 [Hybrid String] Найдено {len(tool_calls)} вызовов в строковом формате")
            return cleaned_text, tool_calls
        
        # Если строковый формат не найден, пробуем старый JSON (для обратной совместимости)
        logger.info("🔧 [Hybrid Fallback] Пробуем JSON-парсинг")
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
        Обрабатывает сообщение пользователя с использованием финальной трехэтапной архитектуры:
        1. Этап 1: Классификация стадии диалога
        2. Этап 2: Мышление (сбор данных через read-only инструменты)
        3. Этап 3: Синтез (финальный ответ с возможными write-действиями)
        
        Args:
            user_id: ID пользователя Telegram
            text: Текст сообщения пользователя
            
        Returns:
            Сгенерированный ответ бота
        """
        logger.info("🎯 DIALOG: Начало обработки сообщения пользователя")
        logger.info(f"👤 DIALOG: Пользователь ID: {user_id}")
        logger.info(f"💬 DIALOG: Сообщение: '{text}'")
        
        # Логируем начало обработки диалога
        log_dialog_start(logger, user_id, text)
        
        # Получаем или создаем контекст для текущего пользователя
        session_context = self.session_contexts.setdefault(user_id, {})
        
        # Получаем или создаем контекст диалога для текущего пользователя
        dialog_context = self.dialog_contexts.setdefault(user_id, {})
        
        # Создаем трейсер для этого диалога
        tracer = DialogueTracer(user_id=user_id, user_message=text)
        
        try:
            # 0. Загружаем (или создаем) клиента
            logger.debug("--- [ASYNC DB] Вызов get_or_create_by_telegram_id...")
            client = await asyncio.to_thread(self.client_repository.get_or_create_by_telegram_id, user_id)
            logger.debug("--- [ASYNC DB] ...get_or_create_by_telegram_id ЗАВЕРШЕН.")
            decoded_first_name = self._decode_string_field(client['first_name']) if client['first_name'] else None
            decoded_phone = self._decode_string_field(client['phone_number']) if client['phone_number'] else None
            tracer.add_event("👤 Клиент загружен", f"ID клиента: {client['id']}, Имя: {decoded_first_name}, Телефон: {decoded_phone}")
            
            # 1. Получаем историю диалога (окно контекста - последние N сообщений)
            logger.debug(f"--- [ASYNC DB] Вызов get_recent_messages для user_id={user_id}...")
            history_records = await asyncio.to_thread(self.repository.get_recent_messages, user_id, limit=self.CONTEXT_WINDOW_SIZE)
            logger.debug(f"--- [ASYNC DB] ...get_recent_messages ЗАВЕРШЕН. Найдено {len(history_records)} сообщений.")
            tracer.add_event("📚 История диалога загружена", f"Количество сообщений: {len(history_records)} (окно контекста: {self.CONTEXT_WINDOW_SIZE})")
            
            # Преобразуем историю в расширенный формат для Gemini
            dialog_history: List[Dict] = []
            for record in history_records:
                role = "user" if record['role'] == "user" else "model"
                decoded_message_text = self._decode_string_field(record['message_text'])
                dialog_history.append({
                    "role": role,
                    "parts": [{"text": decoded_message_text}]
                })
            
            # 2. Сохраняем новое сообщение пользователя в БД
            logger.debug(f"--- [ASYNC DB] Вызов add_message (роль: user) для user_id={user_id}...")
            await asyncio.to_thread(self.repository.add_message, user_id=user_id, role="user", message_text=text)
            logger.debug(f"--- [ASYNC DB] ...add_message (роль: user) ЗАВЕРШЕН.")
            tracer.add_event("💾 Сообщение сохранено в БД", f"Роль: user, Текст: {text}")
            
            # === ЭТАП 1: КЛАССИФИКАЦИЯ ===
            tracer.add_event("🔍 Этап 1: Классификация", "Определяем стадию диалога")
            logger.info("🔍 DIALOG: Этап 1 - Классификация стадии диалога")
            
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
            
            # === ПОДГОТОВКА КОНТЕКСТА ДЛЯ ОТМЕНЫ/ПЕРЕНОСА ===
            # Проверяем, нужны ли данные о записях для текущей стадии
            if stage in ['cancellation_request', 'rescheduling']:
                tracer.add_event("🔍 Подготовка контекста для отмены/переноса", f"Стадия: {stage}")
                logger.info(f"🔍 Подготовка контекста для стадии: {stage}")
                
                # Проверяем, есть ли уже данные о записях в сессии
                if 'appointments_in_focus' not in session_context:
                    tracer.add_event("📋 Загрузка записей клиента", "Данные о записях отсутствуют в сессии")
                    logger.info("📋 Загружаем данные о записях клиента")
                    
                    # Получаем структурированные данные записей напрямую из AppointmentService
                    appointments_data = self.appointment_service.get_my_appointments(user_id)
                    
                    # Логируем результат для отладки
                    if appointments_data:
                        logger.info(f"📋 Загружено {len(appointments_data)} записей для скрытого контекста")
                        for appointment in appointments_data:
                            logger.info(f"📅 Запись: ID={appointment['id']}, {appointment['details']}")
                    else:
                        logger.info("📭 У клиента нет предстоящих записей")
                    
                    session_context['appointments_in_focus'] = appointments_data
                    
                    tracer.add_event("✅ Записи загружены в память", {
                        "appointments_count": len(appointments_data),
                        "appointments_data": appointments_data
                    })
                    logger.info(f"✅ Записи сохранены в память: {len(appointments_data)} записей")
                else:
                    tracer.add_event("✅ Записи уже в памяти", f"Количество записей: {len(session_context['appointments_in_focus'])}")
                    logger.info("✅ Данные о записях уже есть в сессии")
            
            # Быстрый путь для конфликтных ситуаций
            if stage == 'conflict_escalation':
                logger.warning(f"⚠️ КОНФЛИКТНАЯ СТАДИЯ: Немедленная эскалация на менеджера")
                
                tracer.add_event("⚠️ Конфликтная ситуация", "Эскалация на менеджера")
                
                # Вызываем менеджера с текстом сообщения пользователя как причиной
                manager_response = self.tool_service.call_manager(text)
                
                tracer.add_event("👨‍💼 Вызов менеджера", f"Ответ: {manager_response['response_to_user']}")
                logger.info(f"👨‍💼 Действие: эскалация на менеджера")
                
                # Сохраняем ответ бота в БД
                logger.debug(f"--- [ASYNC DB] Вызов add_message (роль: model) для user_id={user_id} (manager response)...")
                await asyncio.to_thread(self.repository.add_message, user_id=user_id, role="model", message_text=manager_response['response_to_user'])
                logger.debug(f"--- [ASYNC DB] ...add_message (роль: model, manager) ЗАВЕРШЕН.")
                
                tracer.add_event("💾 Ответ менеджера сохранен", f"Текст: {manager_response['response_to_user']}")
                
                # Логируем завершение обработки
                log_dialog_end(logger, manager_response['response_to_user'])
                
                # Возвращаем ответ пользователю и завершаем обработку
                return manager_response['response_to_user']
            
            # === ЭТАП 2: МЫШЛЕНИЕ ===
            tracer.add_event("🧠 Этап 2: Мышление", "Сбор данных через read-only инструменты")
            logger.info("🧠 DIALOG: Этап 2 - Мышление (сбор данных через инструменты)")
            
            # Извлекаем доступные инструменты для текущей стадии
            stage_data = self.prompt_builder.dialogue_patterns.get(stage, {})
            available_tools = stage_data.get('available_tools', [])
            
            # Формируем промпт для мышления
            # Добавляем скрытый контекст для стадий отмены/переноса
            hidden_context = ""
            if stage in ['cancellation_request', 'rescheduling'] and 'appointments_in_focus' in session_context:
                appointments_data = session_context['appointments_in_focus']
                if appointments_data:
                    hidden_context = f"\n\n## СКРЫТЫЙ КОНТЕКСТ (только для тебя):\n"
                    hidden_context += f"Записи клиента с ID для операций:\n"
                    for appointment in appointments_data:
                        hidden_context += f"- ID: {appointment['id']}, {appointment['details']}\n"
                    
                    # Логируем формирование скрытого контекста
                    tracer.add_event("🔍 Скрытый контекст сформирован", {
                        "stage": stage,
                        "appointments_count": len(appointments_data),
                        "hidden_context": hidden_context
                    })
                    logger.info(f"🔍 Сформирован скрытый контекст для стадии {stage}: {len(appointments_data)} записей")
                else:
                    tracer.add_event("📭 Нет записей для скрытого контекста", f"Стадия: {stage}, Записей: 0")
                    logger.info(f"📭 Нет записей для формирования скрытого контекста на стадии {stage}")
            else:
                tracer.add_event("ℹ️ Скрытый контекст не нужен", f"Стадия: {stage}")
                logger.info(f"ℹ️ Скрытый контекст не формируется для стадии {stage}")
            
            thinking_prompt = self.prompt_builder.build_thinking_prompt(
                        stage_name=stage,
                        history=dialog_history,
                        user_message=text,
                        client_name=client['first_name'],
                        client_phone_saved=bool(client['phone_number']),
                        hidden_context=hidden_context
                    )
            
            tracer.add_event("📝 Промпт мышления сформирован", {
                "prompt_length": len(thinking_prompt),
                "stage": stage,
                "hidden_context_length": len(hidden_context),
                "has_hidden_context": bool(hidden_context)
            })
                
            # Создаем историю для второго вызова LLM
            thinking_history = [
                    {
                        "role": "user",
                    "parts": [{"text": thinking_prompt}]
                }
            ]
            
            # Второй вызов LLM для мышления (с отфильтрованными инструментами)
            filtered_tools = self._get_filtered_tools(available_tools)
            thinking_response = await self.llm_service.generate_response(thinking_history, filtered_tools, tracer=tracer)
            
            tracer.add_event("✅ Ответ мышления получен", {
                "response_length": len(thinking_response),
                "response": thinking_response
            })
            logger.info(f"✅ Ответ мышления получен")
            
            # Парсим ответ мышления
            tracer.add_event("🔍 Парсинг ответа мышления", f"Длина ответа: {len(thinking_response)}")
            logger.info(f"🔍 Парсинг ответа мышления")
            
            # Сначала пробуем новый строковый формат, потом JSON
            cleaned_text, tool_calls = self.parse_string_format_response(thinking_response)
            if not tool_calls:
                # Если строковый формат не найден, пробуем JSON
                cleaned_text, tool_calls = self.parse_hybrid_response(thinking_response)
            
            # Извлекаем и сохраняем сущности из tool_calls и исходного сообщения
            if tool_calls:
                self.extract_and_save_entities(tool_calls, text, dialog_context, tracer)
                tracer.add_event("🔍 Сущности извлечены и сохранены", {
                    "dialog_context": dialog_context,
                    "tool_calls_count": len(tool_calls)
                })
            
            # Переменная для результатов инструментов
            tool_results = ""
            
            # Если есть вызовы инструментов - выполняем их
            if tool_calls:
                tracer.add_event("⚙️ Выполнение разведывательных инструментов", {
                    "tool_calls": tool_calls,
                    "tool_calls_count": len(tool_calls),
                    "cleaned_text_length": len(cleaned_text)
                })
                logger.info(f"⚙️ Выполнение {len(tool_calls)} разведывательных инструментов")
                
                # Выполняем инструменты
                iteration_results = []
                for tool_call in tool_calls:
                    tool_name = tool_call.get('tool_name')
                    parameters = tool_call.get('parameters', {})
                    
                    # Преобразуем типы параметров для надежности
                    parameters = self._convert_parameter_types(parameters)
                    
                    # Добавляем user_telegram_id к параметрам для инструментов, которые его требуют
                    if tool_name in ['cancel_appointment_by_id', 'reschedule_appointment_by_id']:
                        parameters['user_telegram_id'] = user_id
                    
                    tracer.add_event(f"🔧 Выполнение разведывательного инструмента", f"Инструмент: {tool_name}, Параметры: {parameters}")
                    
                    try:
                        # Выполняем инструмент через ToolOrchestratorService с контекстом и трассировкой
                        tool_result = await self.tool_orchestrator.execute_single_tool(tool_name, parameters, user_id, dialog_context, tracer)
                        iteration_results.append(f"Результат {tool_name}: {tool_result}")
                        
                        # Специальная трассировка для операций с записями
                        if tool_name == 'get_my_appointments':
                            # Данные уже загружены на этапе подготовки контекста
                            logger.info(f"🔍 Инструмент get_my_appointments выполнен (данные уже в памяти)")
                            tracer.add_event("🔍 Инструмент get_my_appointments выполнен", "Данные уже загружены в память")
                        
                        tracer.add_event(f"✅ Разведывательный инструмент выполнен", f"Инструмент: {tool_name}, Результат: {tool_result}")
                        logger.info(f"✅ Разведывательный инструмент выполнен: {tool_name}")
                        
                    except Exception as e:
                        error_msg = f"Ошибка выполнения {tool_name}: {str(e)}"
                        iteration_results.append(error_msg)
                        tracer.add_event(f"❌ Ошибка разведывательного инструмента", f"Инструмент: {tool_name}, Ошибка: {str(e)}")
                        logger.error(f"❌ Ошибка выполнения разведывательного инструмента {tool_name}: {e}")
                
                # Формируем результаты инструментов
                if iteration_results:
                    tool_results = "\n".join(iteration_results)
            
            # Если есть текстовый ответ на этапе мышления - это финальный ответ
            if cleaned_text.strip():
                bot_response_text = cleaned_text.strip()
                tracer.add_event("✅ Финальный ответ получен на этапе мышления", {
                    "response": bot_response_text,
                    "length": len(bot_response_text)
                })
                logger.info("✅ Финальный ответ получен на этапе мышления")
                
                # Сохраняем финальный ответ бота в БД
                logger.debug(f"--- [ASYNC DB] Вызов add_message (роль: model) для user_id={user_id} (thinking stage)...")
                await asyncio.to_thread(self.repository.add_message, user_id=user_id, role="model", message_text=bot_response_text)
                logger.debug(f"--- [ASYNC DB] ...add_message (роль: model, thinking) ЗАВЕРШЕН.")
                
                tracer.add_event("💾 Финальный ответ сохранен", {
                    "text": bot_response_text,
                    "length": len(bot_response_text)
                })
                
                # Логируем завершение обработки
                log_dialog_end(logger, bot_response_text)
                
                # Возвращаем сгенерированный текст
                return bot_response_text
            
            # === ЭТАП 3: СИНТЕЗ ===
            tracer.add_event("🎯 Этап 3: Синтез", "Формирование финального ответа с возможными действиями")
            logger.info("🎯 DIALOG: Этап 3 - Синтез (формирование финального ответа)")
            
            # Формируем промпт для синтеза
            # Передаем тот же скрытый контекст, что использовался на этапе мышления
            synthesis_prompt = self.prompt_builder.build_synthesis_prompt(
                stage_name=stage,
                history=dialog_history,
                user_message=text,
                tool_results=tool_results,
                client_name=client['first_name'],
                client_phone_saved=bool(client['phone_number']),
                hidden_context=hidden_context
            )
            
            tracer.add_event("📝 Промпт синтеза сформирован", {
                "prompt_length": len(synthesis_prompt),
                "tool_results_length": len(tool_results),
                "stage": stage,
                "hidden_context_length": len(hidden_context),
                "has_hidden_context": bool(hidden_context)
            })
            
            # Создаем историю для третьего вызова LLM
            synthesis_history = [
                {
                    "role": "user",
                    "parts": [{"text": synthesis_prompt}]
                }
            ]
            
            # Третий вызов LLM для синтеза (с отфильтрованными инструментами)
            filtered_tools = self._get_filtered_tools(available_tools)
            synthesis_response = await self.llm_service.generate_response(synthesis_history, filtered_tools, tracer=tracer)
            
            tracer.add_event("✅ Ответ синтеза получен", {
                "response_length": len(synthesis_response),
                "response": synthesis_response
            })
            logger.info(f"✅ Ответ синтеза получен")
            
            # Парсим ответ синтеза
            tracer.add_event("🔍 Парсинг ответа синтеза", f"Длина ответа: {len(synthesis_response)}")
            logger.info(f"🔍 Парсинг ответа синтеза")
            
            # Сначала пробуем новый строковый формат, потом JSON
            cleaned_text, tool_calls = self.parse_string_format_response(synthesis_response)
            if not tool_calls:
                # Если строковый формат не найден, пробуем JSON
                cleaned_text, tool_calls = self.parse_hybrid_response(synthesis_response)
            
            # Извлекаем и сохраняем сущности из tool_calls и исходного сообщения
            if tool_calls:
                self.extract_and_save_entities(tool_calls, text, dialog_context, tracer)
                tracer.add_event("🔍 Сущности извлечены и сохранены (синтез)", {
                    "dialog_context": dialog_context,
                    "tool_calls_count": len(tool_calls)
                })
            
            # Если есть вызовы инструментов - выполняем их
            if tool_calls:
                tracer.add_event("⚙️ Выполнение исполнительных инструментов", {
                    "tool_calls": tool_calls,
                    "tool_calls_count": len(tool_calls),
                    "cleaned_text_length": len(cleaned_text)
                })
                logger.info(f"⚙️ Выполнение {len(tool_calls)} исполнительных инструментов")
                
                # Выполняем инструменты
                for tool_call in tool_calls:
                    tool_name = tool_call.get('tool_name')
                    parameters = tool_call.get('parameters', {})
                    
                    # Преобразуем типы параметров для надежности
                    parameters = self._convert_parameter_types(parameters)
                    
                    # Добавляем user_telegram_id к параметрам для инструментов, которые его требуют
                    if tool_name in ['cancel_appointment_by_id', 'reschedule_appointment_by_id']:
                        parameters['user_telegram_id'] = user_id
                    
                    tracer.add_event(f"🔧 Выполнение исполнительного инструмента", f"Инструмент: {tool_name}, Параметры: {parameters}")
                    
                    try:
                        # Выполняем инструмент через ToolOrchestratorService с контекстом и трассировкой
                        tool_result = await self.tool_orchestrator.execute_single_tool(tool_name, parameters, user_id, dialog_context, tracer)
                        
                        # Проверяем результат для критических операций
                        if tool_name in ['cancel_appointment_by_id', 'reschedule_appointment_by_id']:
                            if "Ошибка:" in tool_result or "не найдена" in tool_result or "нет прав" in tool_result:
                                tracer.add_event(f"❌ Критическая ошибка инструмента", f"Инструмент: {tool_name}, Результат: {tool_result}")
                                logger.error(f"❌ Критическая ошибка инструмента {tool_name}: {tool_result}")
                                # Не продолжаем выполнение, если операция не удалась
                                bot_response_text = tool_result
                                break
                        
                        tracer.add_event(f"✅ Исполнительный инструмент выполнен", f"Инструмент: {tool_name}, Результат: {tool_result}")
                        logger.info(f"✅ Исполнительный инструмент выполнен: {tool_name}")
                        
                    except Exception as e:
                        tracer.add_event(f"❌ Ошибка исполнительного инструмента", f"Инструмент: {tool_name}, Ошибка: {str(e)}")
                        logger.error(f"❌ Ошибка выполнения исполнительного инструмента {tool_name}: {e}")
                        # Для критических операций прерываем выполнение при ошибке
                        if tool_name in ['cancel_appointment_by_id', 'reschedule_appointment_by_id']:
                            bot_response_text = f"Произошла ошибка при выполнении операции. Пожалуйста, обратитесь к менеджеру."
                            break
            
            # Финальный ответ - это очищенный текст
            bot_response_text = cleaned_text.strip()
            
            # Если нет текста, генерируем fallback
            if not bot_response_text:
                tracer.add_event("⚠️ Fallback ответ", "Нет текста в ответе синтеза")
                logger.warning("⚠️ Нет текста в ответе синтеза, генерируем fallback")
                
                # Специальная обработка для стадии view_booking с пустым результатом
                if stage == 'view_booking':
                    # Проверяем, был ли вызван get_my_appointments и вернул ли он пустой результат
                    if 'appointments_in_focus' in session_context:
                        appointments_data = session_context['appointments_in_focus']
                        if not appointments_data:  # Пустой список означает "нет записей"
                            tracer.add_event("📭 Специальная обработка пустого результата", "У клиента нет записей")
                            logger.info("📭 Обрабатываем случай, когда у клиента нет записей")
                            bot_response_text = "У вас нет предстоящих записей."
                        else:
                            # Есть записи, но что-то пошло не так с синтезом
                            fallback_prompt = f"Клиент написал: '{text}'. Сформулируй вежливый ответ, что ты понял его запрос и готов помочь."
                            fallback_history = [
                                {
                                    "role": "user",
                                    "parts": [{"text": fallback_prompt}]
                                }
                            ]
                            bot_response_text = await self.llm_service.generate_response(fallback_history, tracer=tracer)
                    else:
                        # Нет данных о записях в контексте, используем обычный fallback
                        fallback_prompt = f"Клиент написал: '{text}'. Сформулируй вежливый ответ, что ты понял его запрос и готов помочь."
                        fallback_history = [
                            {
                                "role": "user",
                                "parts": [{"text": fallback_prompt}]
                            }
                        ]
                        bot_response_text = await self.llm_service.generate_response(fallback_history, tracer=tracer)
                else:
                    # Для других стадий используем обычный fallback
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
            logger.debug(f"--- [ASYNC DB] Вызов add_message (роль: model) для user_id={user_id} (final stage)...")
            await asyncio.to_thread(self.repository.add_message, user_id=user_id, role="model", message_text=bot_response_text)
            logger.debug(f"--- [ASYNC DB] ...add_message (роль: model, final) ЗАВЕРШЕН.")
            
            tracer.add_event("💾 Финальный ответ сохранен", {
                "text": bot_response_text,
                "length": len(bot_response_text)
            })
            
            # Логируем завершение обработки
            log_dialog_end(logger, bot_response_text)
            logger.info("✅ DIALOG: Обработка сообщения завершена успешно")
            logger.info(f"📤 DIALOG: Финальный ответ: '{bot_response_text[:100]}...'")
            
            # Возвращаем сгенерированный текст
            return bot_response_text
            
        except Exception as e:
            logger.error("💥 DIALOG: Произошла ошибка при обработке сообщения")
            logger.error(f"❌ DIALOG: Тип ошибки: {type(e).__name__}")
            logger.error(f"❌ DIALOG: Сообщение об ошибке: {str(e)}")
            
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