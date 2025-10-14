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
        
        # Получаем модель Gemini 2.5 Flash с инструментами
        self._model = genai.GenerativeModel("gemini-2.5-flash", tools=[salon_tools])
        
        # Сохраняем описания инструментов
        self.tools = salon_tools

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

    def create_chat(self, history: List[Dict]):
        """
        Создает чат с историей для последующего использования.
        
        Args:
            history: Полная история диалога в формате Gemini
            
        Returns:
            Объект чата для взаимодействия с моделью
        """
        return self._model.start_chat(history=history)
    
    async def send_message_to_chat(self, chat, message, user_id: int = None):
        """
        Отправляет сообщение в чат и получает ответ.
        
        Args:
            chat: Объект чата
            message: Сообщение для отправки (строка или список Parts)
            user_id: ID пользователя для логирования
            
        Returns:
            Объект Content с ответом модели
        """
        # Логируем отправляемый запрос
        if user_id is not None:
            request_text = ""
            if isinstance(message, str):
                request_text = message
            elif isinstance(message, list):
                request_text = f"Function Response Parts ({len(message)} parts)"
            else:
                request_text = str(message)
            
            print(f"   🔄 Отправка запроса к Gemini: {request_text[:100]}...")
        
        # Используем asyncio для выполнения синхронного вызова
        loop = asyncio.get_event_loop()
        try:
            response = await loop.run_in_executor(
                None,
                lambda: chat.send_message(message)
            )
        except Exception as e:
            if user_id is not None:
                print(f"   ❌ Ошибка при отправке запроса к Gemini: {str(e)}")
            raise
        
        # Логируем полученный ответ
        if user_id is not None:
            response_text = ""
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'text') and part.text:
                    response_text += part.text
                elif hasattr(part, 'function_call') and part.function_call:
                    response_text += f"Function Call: {part.function_call.name}"
            
            print(f"   ✅ Получен ответ от Gemini: {response_text[:100]}...")
        
        return response.candidates[0].content

    async def generate_response(self, history: List[Dict]) -> str:
        """
        Генерирует ответ на основе готовой истории диалога.
        Теперь GeminiService является "глупым" исполнителем - просто выполняет запросы.
        
        Args:
            history: Готовая история диалога с системной инструкцией
            
        Returns:
            Текстовый ответ модели
        """
        # Создаем чат с готовой историей
        chat = self.create_chat(history)
        
        # Отправляем сообщение "Ответь" для получения ответа
        response_content = await self.send_message_to_chat(chat, "Ответь")
        
        # Извлекаем текстовый ответ
        for part in response_content.parts:
            if hasattr(part, 'text') and part.text:
                return part.text
        
        return "Извините, не удалось сгенерировать ответ."


# Создаем единственный экземпляр сервиса
gemini_service = None

def get_gemini_service() -> GeminiService:
    """
    Получает единственный экземпляр GeminiService с ленивой инициализацией.
    
    Returns:
        Экземпляр GeminiService
    """
    global gemini_service
    if gemini_service is None:
        gemini_service = GeminiService()
    return gemini_service
