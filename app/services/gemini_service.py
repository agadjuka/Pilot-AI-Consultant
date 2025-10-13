import asyncio
import os
import json
from typing import List, Dict, Optional, TYPE_CHECKING
import google.generativeai as genai
from google.oauth2 import service_account
from app.core.config import settings
from app.utils.debug_logger import gemini_debug_logger
from app.services.tool_definitions import salon_tools

if TYPE_CHECKING:
    from app.services.tool_service import ToolService


class GeminiService:
    """Сервис для взаимодействия с моделью Gemini через Google AI SDK."""
    
    def __init__(self):
        """
        Инициализирует клиент Google AI и модель Gemini.
        Использует учетные данные из переменной окружения GOOGLE_APPLICATION_CREDENTIALS.
        """
        # Загружаем credentials
        credentials = self._load_credentials()
        
        # Конфигурируем Google AI SDK
        genai.configure(credentials=credentials)
        
        # Получаем модель Gemini 2.5 Flash
        self._model = genai.GenerativeModel("gemini-2.5-flash")
        
        # Сохраняем описания инструментов
        self.tools = salon_tools
        
        # Системная инструкция для персоны "Кэт"
        self.system_instruction = """Ты — Кэт, дружелюбный и профессиональный AI-ассистент салона красоты.
Твоя задача — помогать клиентам с записью на услуги, отвечать на вопросы о мастерах и услугах.
Общайся вежливо, по-дружески, но профессионально. Используй эмодзи там, где это уместно.
Если клиент хочет записаться, уточни желаемую услугу, мастера (если есть предпочтения) и удобное время.

У тебя есть доступ к инструментам для получения актуальной информации:
- get_all_services: получить список всех услуг с ценами
- get_masters_for_service: найти мастеров для конкретной услуги
- get_available_slots: получить свободные временные слоты мастера

Используй эти инструменты, чтобы давать точную и актуальную информацию."""

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

    async def generate_response(
        self,
        user_message: str,
        tool_service: "ToolService",
        dialog_history: List[Dict[str, str]] = None
    ) -> str:
        """
        Генерирует ответ модели на основе сообщения пользователя и истории диалога.
        Поддерживает вызов инструментов (Function Calling).
        
        Args:
            user_message: Новое сообщение пользователя
            tool_service: Экземпляр ToolService для выполнения вызовов функций
            dialog_history: История диалога в формате [{"role": "user/model", "text": "..."}, ...]
            
        Returns:
            Текстовый ответ модели
        """
        # Логируем запрос к Gemini
        request_number = gemini_debug_logger.log_request(
            user_message=user_message,
            dialog_history=dialog_history,
            system_instruction=self.system_instruction
        )
        
        # Формируем историю для чата
        history = []
        
        # Добавляем системную инструкцию как первое сообщение от модели
        history.append({
            "role": "model",
            "parts": [self.system_instruction]
        })
        
        # Добавляем историю диалога, если она есть
        if dialog_history:
            for message in dialog_history:
                role = "user" if message["role"] == "user" else "model"
                history.append({
                    "role": role,
                    "parts": [message["text"]]
                })
        
        # Используем asyncio для выполнения синхронного вызова в асинхронном контексте
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            self._generate_content_with_tools,
            history,
            user_message,
            tool_service
        )
        
        # Логируем ответ от Gemini
        gemini_debug_logger.log_response(request_number, response)
        
        return response

    def _generate_content_with_tools(
        self,
        history: List[Dict],
        user_message: str,
        tool_service: "ToolService"
    ) -> str:
        """
        Синхронная обертка для вызова API Gemini с поддержкой инструментов.
        Обрабатывает цикл вызова функций: модель может запросить выполнение функции,
        получить результат и сгенерировать финальный ответ.
        
        Args:
            history: История диалога
            user_message: Новое сообщение пользователя
            tool_service: Экземпляр ToolService для выполнения вызовов функций
            
        Returns:
            Текстовый ответ модели
        """
        # Создаем чат с историей и инструментами
        chat = self._model.start_chat(history=history)
        
        # Отправляем сообщение пользователя с указанием доступных инструментов
        response = chat.send_message(user_message, tools=[self.tools])
        
        # Обрабатываем возможные вызовы функций
        # Модель может вызывать функции несколько раз подряд
        max_iterations = 5  # Защита от бесконечного цикла
        iteration = 0
        
        while iteration < max_iterations:
            # Проверяем, есть ли в ответе вызовы функций
            function_calls = []
            for part in response.parts:
                if hasattr(part, 'function_call') and part.function_call:
                    function_calls.append(part.function_call)
            
            # Если функций нет, значит модель вернула финальный текстовый ответ
            if not function_calls:
                break
            
            # Выполняем все вызванные функции
            function_responses = []
            for function_call in function_calls:
                function_name = function_call.name
                function_args = dict(function_call.args)
                
                # Выполняем функцию через ToolService
                result = self._execute_tool_function(
                    tool_service,
                    function_name,
                    function_args
                )
                
                # Формируем ответ функции для модели
                function_responses.append(
                    genai.protos.Part(
                        function_response=genai.protos.FunctionResponse(
                            name=function_name,
                            response={"result": result}
                        )
                    )
                )
            
            # Отправляем результаты функций обратно модели
            response = chat.send_message(function_responses)
            iteration += 1
        
        # Возвращаем финальный текстовый ответ
        return response.text

    def _execute_tool_function(
        self,
        tool_service: "ToolService",
        function_name: str,
        function_args: Dict
    ) -> str:
        """
        Выполняет вызов функции из ToolService.
        
        Args:
            tool_service: Экземпляр ToolService
            function_name: Имя функции для вызова
            function_args: Аргументы функции
            
        Returns:
            Результат выполнения функции в виде строки
        """
        if function_name == "get_all_services":
            return tool_service.get_all_services()
        
        elif function_name == "get_masters_for_service":
            service_name = function_args.get("service_name", "")
            return tool_service.get_masters_for_service(service_name)
        
        elif function_name == "get_available_slots":
            master_name = function_args.get("master_name", "")
            date = function_args.get("date", "")
            return tool_service.get_available_slots(master_name, date)
        
        else:
            return f"Ошибка: неизвестная функция '{function_name}'"


# Создаем единственный экземпляр сервиса
gemini_service = GeminiService()
