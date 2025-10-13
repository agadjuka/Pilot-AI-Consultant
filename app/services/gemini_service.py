import asyncio
import os
import json
from typing import List, Dict, Optional
import google.generativeai as genai
from google.oauth2 import service_account
from app.core.config import settings
from app.utils.debug_logger import gemini_debug_logger


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
        
        # Системная инструкция для персоны "Ева"
        self.system_instruction = """Ты — Кэт, дружелюбный и профессиональный AI-ассистент салона красоты.
Твоя задача — помогать клиентам с записью на услуги, отвечать на вопросы о мастерах и услугах.
Общайся вежливо, по-дружески, но профессионально. Используй эмодзи там, где это уместно.
Если клиент хочет записаться, уточни желаемую услугу, мастера (если есть предпочтения) и удобное время."""

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
        dialog_history: List[Dict[str, str]] = None
    ) -> str:
        """
        Генерирует ответ модели на основе сообщения пользователя и истории диалога.
        
        Args:
            user_message: Новое сообщение пользователя
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
            self._generate_content_sync,
            history,
            user_message
        )
        
        # Логируем ответ от Gemini
        gemini_debug_logger.log_response(request_number, response)
        
        return response

    def _generate_content_sync(self, history: List[Dict], user_message: str) -> str:
        """
        Синхронная обертка для вызова API Gemini.
        
        Args:
            history: История диалога
            user_message: Новое сообщение пользователя
            
        Returns:
            Текстовый ответ модели
        """
        # Создаем чат с историей (без последнего сообщения пользователя)
        chat = self._model.start_chat(history=history)
        
        # Отправляем сообщение пользователя
        response = chat.send_message(user_message)
        
        return response.text


# Создаем единственный экземпляр сервиса
gemini_service = GeminiService()
