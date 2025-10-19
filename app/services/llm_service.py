import asyncio
import os
import json
import re
from typing import List, Dict, Optional, TYPE_CHECKING, Any
import google.generativeai as genai
from google.oauth2 import service_account
import requests
import logging
from app.core.config import settings
from app.services.tool_definitions import read_only_tools, write_tools, salon_tools

# Получаем логгер для этого модуля
logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from app.services.tool_service import ToolService


class LLMService:
    """Универсальный сервис для взаимодействия с различными LLM провайдерами."""
    
    def __init__(self):
        """
        Инициализирует клиент выбранного LLM провайдера.
        Поддерживает Google Gemini и YandexGPT.
        """
        self.provider = settings.LLM_PROVIDER.lower()
        
        if self.provider == "yandex":
            self._init_yandex_client()
        else:  # по умолчанию Google Gemini
            self._init_gemini_client()
        
        # Сохраняем описания инструментов для обоих провайдеров
        self.tools = salon_tools

    def _init_gemini_client(self):
        """Инициализирует клиент Google Gemini."""
        # Загружаем credentials
        credentials = self._load_credentials()
        
        # Конфигурируем Google AI SDK
        genai.configure(credentials=credentials)
        
        # Модель будет создаваться динамически в create_chat с нужными инструментами

    def _init_yandex_client(self):
        """Инициализирует клиент YandexGPT."""
        if not settings.YANDEX_FOLDER_ID or not settings.YANDEX_API_KEY_SECRET:
            raise ValueError("Для использования YandexGPT необходимо указать YANDEX_FOLDER_ID и YANDEX_API_KEY_SECRET")
        
        self._yandex_folder_id = settings.YANDEX_FOLDER_ID
        self._yandex_api_key = settings.YANDEX_API_KEY_SECRET
        self._yandex_base_url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"

    def _load_credentials(self) -> service_account.Credentials:
        """
        Загружает credentials для Google Cloud.
        Поддерживает 3 варианта загрузки (как в рабочем проекте):
        1. GOOGLE_APPLICATION_CREDENTIALS_JSON - JSON напрямую в переменной
        2. GOOGLE_APPLICATION_CREDENTIALS - путь к файлу или JSON строка
        3. Application Default Credentials (ADC)
        
        Returns:
            Объект Credentials для аутентификации
        """
        # Вариант 1: JSON напрямую в переменной окружения (для Cloud Run)
        credentials_json = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
        if credentials_json:
            credentials_info = json.loads(credentials_json)
            return service_account.Credentials.from_service_account_info(
                credentials_info,
                scopes=["https://www.googleapis.com/auth/generative-language"]
            )
        
        # Вариант 2: Путь к файлу credentials или JSON строка
        credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if credentials_path:
            # Проверяем, это путь к файлу или JSON строка
            if os.path.isfile(credentials_path):
                return service_account.Credentials.from_service_account_file(
                    credentials_path,
                    scopes=["https://www.googleapis.com/auth/generative-language"]
                )
            else:
                # Пробуем распарсить как JSON
                try:
                    credentials_info = json.loads(credentials_path)
                    return service_account.Credentials.from_service_account_info(
                        credentials_info,
                        scopes=["https://www.googleapis.com/auth/generative-language"]
                    )
                except json.JSONDecodeError:
                    raise ValueError(f"GOOGLE_APPLICATION_CREDENTIALS не является валидным путем или JSON: {credentials_path}")
        
        # Вариант 3: Application Default Credentials (для Cloud Run)
        import google.auth
        credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/generative-language"]
        )
        return credentials

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

    def create_chat(self, history: List[Dict], tools=None):
        """
        Создает чат с историей для последующего использования.
        
        Args:
            history: Полная история диалога в формате провайдера
            tools: Набор инструментов для использования (по умолчанию все инструменты)
            
        Returns:
            Объект чата для взаимодействия с моделью
        """
        if self.provider == "yandex":
            # Для YandexGPT возвращаем историю как есть
            return history
        else:
            # Для Gemini создаем объект чата с указанными инструментами
            if tools is None:
                tools = salon_tools
            model = genai.GenerativeModel("gemini-2.5-flash", tools=[tools])
            return model.start_chat(history=history)
    
    async def send_message_to_chat(self, chat, message, user_id: int = None):
        """
        Отправляет сообщение в чат и получает ответ.
        
        Args:
            chat: Объект чата или история сообщений
            message: Сообщение для отправки (строка или список Parts)
            user_id: ID пользователя для логирования
            
        Returns:
            Объект Content с ответом модели
        """
        if self.provider == "yandex":
            return await self._send_yandex_message(chat, message, user_id)
        else:
            return await self._send_gemini_message(chat, message, user_id)

    async def _send_gemini_message(self, chat, message, user_id: int = None):
        """Отправляет сообщение в Gemini чат."""
        # Логируем только ошибки
        
        # Используем asyncio для выполнения синхронного вызова
        loop = asyncio.get_event_loop()
        try:
            response = await loop.run_in_executor(
                None,
                lambda: chat.send_message(message)
            )
        except Exception as e:
            logger.error(f"❌ [Gemini] Ошибка: {str(e)}")
            raise
        
        # Логируем только ошибки
        
        return response.candidates[0].content

    async def _send_yandex_message(self, history: List[Dict], message, user_id: int = None):
        """Отправляет сообщение в YandexGPT."""
        # Логируем только ошибки
        
        # Обрабатываем message - может быть строкой или списком объектов Part
        if isinstance(message, str):
            message_text = message
        elif isinstance(message, list):
            # Извлекаем текст из объектов Part
            message_parts = []
            for part in message:
                if hasattr(part, 'text') and part.text:
                    message_parts.append(part.text)
                elif hasattr(part, 'function_response') and part.function_response:
                    func_name = part.function_response.name
                    func_response = part.function_response.response
                    message_parts.append(f"Результат функции {func_name}: {func_response}")
            message_text = " ".join(message_parts)
        else:
            message_text = str(message)
        
        # Если history уже в формате YandexGPT, используем как есть
        if history and isinstance(history[0], dict) and "text" in history[0]:
            updated_history = history.copy()
            updated_history.append({
                "role": "user",
                "text": message_text
            })
        else:
            # Преобразуем Gemini формат в YandexGPT формат
            updated_history = self._enhance_history_for_yandex(history)
            updated_history.append({
                "role": "user",
                "text": message_text
            })
        
        # Формируем запрос к YandexGPT API
        payload = {
            "modelUri": f"gpt://{self._yandex_folder_id}/yandexgpt",
            "completionOptions": {
                "stream": False,
                "temperature": 0.6,
                "maxTokens": 2000
            },
            "messages": updated_history
        }
        
        headers = {
            "Authorization": f"Api-Key {self._yandex_api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            # Используем asyncio для выполнения HTTP запроса
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.post(self._yandex_base_url, json=payload, headers=headers)
            )
            
            # Логируем только ошибки
            if response.status_code != 200:
                logger.error(f"❌ [Yandex] Ошибка HTTP {response.status_code}: {response.text[:120]}")
            
            response.raise_for_status()
            
            result = response.json()
            # Логируем только ошибки
            
            # Возвращаем ответ в формате, совместимом с Gemini
            return self._format_yandex_response(result)
            
        except Exception as e:
            logger.error(f"❌ [Yandex] Ошибка: {str(e)}")
            raise

    def _format_yandex_response(self, yandex_result: Dict) -> Any:
        """
        Форматирует ответ YandexGPT в формат, совместимый с Gemini.
        
        Args:
            yandex_result: Ответ от YandexGPT API
            
        Returns:
            Объект, имитирующий структуру ответа Gemini
        """
        alternatives = yandex_result.get("result", {}).get("alternatives", [])
        if not alternatives:
            return None
        
        text = alternatives[0].get("message", {}).get("text", "")
        
        # Проверяем, есть ли вызовы функций в ответе (новый JSON формат)
        try:
            # Пытаемся распарсить как JSON массив
            import json
            tool_calls = json.loads(text)
            if isinstance(tool_calls, list) and len(tool_calls) > 0:
                # Создаем объекты, имитирующие function_call от Gemini для каждого вызова
                mock_parts = []
                for tool_call in tool_calls:
                    if isinstance(tool_call, dict) and "tool_name" in tool_call:
                        function_name = tool_call["tool_name"]
                        function_args = tool_call.get("parameters", {})
                        
                        class MockFunctionCall:
                            def __init__(self, name, args):
                                self.name = name
                                self.args = args
                        
                        class MockPart:
                            def __init__(self, function_call):
                                self.function_call = function_call
                        
                        mock_parts.append(MockPart(MockFunctionCall(function_name, function_args)))
                
                if mock_parts:
                    class MockContent:
                        def __init__(self, parts):
                            self.parts = parts
                    
                    return MockContent(mock_parts)
        except (json.JSONDecodeError, ValueError, KeyError):
            # Если не удалось распарсить как JSON, пробуем старый формат
            pass
        
        # Проверяем старый формат [TOOL: ...] для обратной совместимости
        tool_call_match = re.search(r'\[TOOL:\s*(\w+)\((.*?)\)\]', text)
        if tool_call_match:
            function_name = tool_call_match.group(1)
            function_args_str = tool_call_match.group(2)
            
            # Парсим аргументы функции
            try:
                function_args = json.loads(f"{{{function_args_str}}}") if function_args_str else {}
            except json.JSONDecodeError:
                function_args = {}
            
            # Создаем объект, имитирующий function_call от Gemini
            class MockFunctionCall:
                def __init__(self, name, args):
                    self.name = name
                    self.args = args
            
            class MockPart:
                def __init__(self, function_call):
                    self.function_call = function_call
            
            class MockContent:
                def __init__(self, parts):
                    self.parts = parts
            
            return MockContent([MockPart(MockFunctionCall(function_name, function_args))])
        
        # Обычный текстовый ответ
        class MockTextPart:
            def __init__(self, text):
                self.text = text
        
        class MockContent:
            def __init__(self, parts):
                self.parts = parts
        
        return MockContent([MockTextPart(text)])

    async def generate_response(self, history: List[Dict], tools=None, tracer=None) -> str:
        """
        Генерирует ответ на основе готовой истории диалога.
        Поддерживает как Gemini, так и YandexGPT.
        
        Args:
            history: Готовая история диалога с системной инструкцией
            tools: Набор инструментов для использования (по умолчанию все инструменты)
            tracer: Объект DialogueTracer для логирования промптов и ответов
            
        Returns:
            Текстовый ответ модели
        """
        if self.provider == "yandex":
            return await self._generate_yandex_response(history, tracer)
        else:
            return await self._generate_gemini_response(history, tools, tracer)

    async def _generate_gemini_response(self, history: List[Dict], tools=None, tracer=None) -> str:
        """Генерирует ответ через Gemini."""
        # Логируем промпт, если есть tracer
        if tracer:
            tracer.add_event("🤖 Вызов Gemini", {
                "provider": "Google Gemini",
                "history_length": len(history),
                "tools_enabled": tools is not None,
                "prompt": history[-1]["parts"][0]["text"] if history and "parts" in history[-1] else "Системный промпт"
            })
        
        # Создаем чат с готовой историей и указанными инструментами
        chat = self.create_chat(history, tools)
        
        # Отправляем сообщение "Ответь" для получения ответа
        response_content = await self.send_message_to_chat(chat, "Ответь")
        
        # Извлекаем текстовый ответ
        response_text = ""
        for part in response_content.parts:
            if hasattr(part, 'text') and part.text:
                response_text += part.text
        
        # Логируем ответ, если есть tracer
        if tracer:
            tracer.add_event("🤖 Ответ Gemini получен", {
                "provider": "Google Gemini",
                "response_length": len(response_text),
                "response": response_text[:500] + "..." if len(response_text) > 500 else response_text
            })
        
        return response_text if response_text else "Извините, не удалось сгенерировать ответ."

    async def _generate_yandex_response(self, history: List[Dict], tracer=None) -> str:
        """Генерирует ответ через YandexGPT."""
        # Добавляем инструкцию для function calling в системный промпт
        enhanced_history = self._enhance_history_for_yandex(history)
        
        # Логируем промпт, если есть tracer
        if tracer:
            tracer.add_event("🤖 Вызов YandexGPT", {
                "provider": "YandexGPT",
                "history_length": len(enhanced_history),
                "enhanced_history": enhanced_history
            })
        
        # Отправляем сообщение "Ответь" для получения ответа
        response_content = await self.send_message_to_chat(enhanced_history, "Ответь")
        
        # Извлекаем текстовый ответ
        response_text = ""
        for part in response_content.parts:
            if hasattr(part, 'text') and part.text:
                response_text += part.text
        
        # Логируем ответ, если есть tracer
        if tracer:
            tracer.add_event("🤖 Ответ YandexGPT получен", {
                "provider": "YandexGPT",
                "response_length": len(response_text),
                "response": response_text[:500] + "..." if len(response_text) > 500 else response_text
            })
        
        return response_text if response_text else "Извините, не удалось сгенерировать ответ."

    def _enhance_history_for_yandex(self, history: List[Dict]) -> List[Dict]:
        """
        Улучшает историю диалога для YandexGPT, добавляя инструкции по function calling.
        
        Args:
            history: Исходная история диалога
            
        Returns:
            Улучшенная история с инструкциями для function calling
        """
        enhanced_history = []
        
        # Преобразуем историю в формат YandexGPT
        for message in history:
            if message.get("role") == "system":
                system_text = message.get("text", "")
                
                # Добавляем инструкции по function calling (новый строковый формат)
                function_calling_instructions = """

ВАЖНО: Если нужно вызвать инструмент(ы), используй новый строковый формат TOOL_CALL:
`TOOL_CALL: имя_инструмента(параметр1="значение1", параметр2="значение2")`

Доступные инструменты:
- get_all_services — вернуть список услуг
- get_masters_for_service — мастера для услуги (service_name)
- get_available_slots — свободные окна (service_name, date)
- create_appointment — создать запись (master_name, service_name, date, time, client_name)
- get_my_appointments — мои предстоящие записи
- cancel_appointment_by_id — отменить запись (appointment_id) — ВАЖНО: используй именно "appointment_id", не "id"
- reschedule_appointment_by_id — перенести запись (appointment_id, new_date, new_time) — ВАЖНО: используй именно "appointment_id", не "id"
- call_manager — позвать менеджера (reason)

Правила вызова инструментов:
1) Ты можешь вызывать НЕСКОЛЬКО инструментов ОДНОВРЕМЕННО, если запрос клиента сложный.
2) Когда пользователь подтверждает запись, НЕМЕДЛЕННО вызывайте create_appointment с известными параметрами.
3) Если в системном контексте указано, что имя и/или телефон клиента сохранены в БД, НЕ задавайте вопросы об этих данных — сразу создавайте запись.

Примеры:
- Один инструмент: `TOOL_CALL: get_available_slots(service_name="Маникюр", date="2025-10-15")`
- Несколько инструментов:
`TOOL_CALL: get_all_services()`
`TOOL_CALL: get_available_slots(service_name="Маникюр", date="завтра")`

НИКОГДА не отвечайте обычным текстом, если по логике нужно вызвать инструмент!
"""
                
                enhanced_history.append({
                    "role": "system",
                    "text": system_text + function_calling_instructions
                })
            elif message.get("role") in ["user", "model"]:
                # Преобразуем Gemini формат в YandexGPT формат
                text_content = ""
                if "parts" in message:
                    for part in message["parts"]:
                        if isinstance(part, dict) and "text" in part:
                            text_content += self._decode_string_field(part["text"])
                        elif hasattr(part, 'text'):
                            text_content += self._decode_string_field(part.text)
                else:
                    text_content = self._decode_string_field(message.get("text", ""))
                
                role = "assistant" if message.get("role") == "model" else "user"
                enhanced_history.append({
                    "role": role,
                    "text": text_content
                })
        
        return enhanced_history


# Создаем единственный экземпляр сервиса
llm_service = None

def get_llm_service() -> LLMService:
    """
    Получает единственный экземпляр LLMService с ленивой инициализацией.
    
    Returns:
        Экземпляр LLMService
    """
    global llm_service
    if llm_service is None:
        llm_service = LLMService()
    return llm_service

# Обратная совместимость
def get_gemini_service() -> LLMService:
    """
    Получает экземпляр LLMService для обратной совместимости.
    
    Returns:
        Экземпляр LLMService
    """
    return get_llm_service()
