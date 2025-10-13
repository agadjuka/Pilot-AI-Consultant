import asyncio
import os
import json
from datetime import datetime
from zoneinfo import ZoneInfo
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
        
        # Базовая системная инструкция для персоны "Кэт"
        self.system_instruction_template = """Ты — Кэт, дружелюбный и профессиональный AI-ассистент салона красоты.
Твоя задача — помогать клиентам с записью на услуги, отвечать на вопросы о мастерах и услугах.
Общайся вежливо, по-дружески, но профессионально. Используй эмодзи там, где это уместно.
Если клиент хочет записаться, уточни желаемую услугу, мастера (если есть предпочтения) и удобное время.

{current_datetime}

Учитывай указанную выше дату и время при определении любых дат и временных интервалов в диалоге.

ВАЖНО: Всегда используй инструмент get_all_services перед тем, как предлагать клиенту конкретные услуги или варианты. 
Не предлагай услуги, которых нет в реальном списке. Если клиент спрашивает о чем-то неопределенном 
(например, "ламинирование"), сначала получи полный список услуг, а затем предложи конкретные варианты из этого списка.

У тебя есть доступ к инструментам для получения актуальной информации:
- get_all_services: получить список всех услуг с ценами (ИСПОЛЬЗУЙ ПЕРВЫМ!)
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

    def create_chat(self, history: List[Dict]):
        """
        Создает чат с историей для последующего использования.
        
        Args:
            history: Полная история диалога в формате Gemini
            
        Returns:
            Объект чата для взаимодействия с моделью
        """
        return self._model.start_chat(history=history)
    
    async def send_message_to_chat(self, chat, message):
        """
        Отправляет сообщение в чат и получает ответ.
        
        Args:
            chat: Объект чата
            message: Сообщение для отправки (строка или список Parts)
            
        Returns:
            Объект Content с ответом модели
        """
        # Используем asyncio для выполнения синхронного вызова
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: chat.send_message(message)
        )
        
        return response.candidates[0].content

    def _get_current_datetime_info(self) -> str:
        """
        Получает текущую дату и время в московском часовом поясе.
        
        Returns:
            Отформатированная строка с датой, временем и днем недели
        """
        moscow_tz = ZoneInfo('Europe/Moscow')
        now = datetime.now(moscow_tz)
        
        # Дни недели на русском
        weekdays = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье']
        weekday = weekdays[now.weekday()]
        
        # Форматируем дату и время
        return f"Сегодня: {weekday}, {now.strftime('%d.%m.%Y')}, время: {now.strftime('%H:%M')}"
    
    def build_history_with_system_instruction(self, dialog_history: List[Dict] = None) -> List[Dict]:
        """
        Формирует историю для чата, добавляя системную инструкцию с текущей датой.
        
        Args:
            dialog_history: История диалога в расширенном формате
            
        Returns:
            Список сообщений в формате Gemini API
        """
        # Формируем историю для чата
        history = []
        
        # Получаем текущую дату и время
        current_datetime_info = self._get_current_datetime_info()
        
        # Подставляем текущую дату в системную инструкцию
        system_instruction = self.system_instruction_template.format(
            current_datetime=current_datetime_info
        )
        
        # Добавляем системную инструкцию как первое сообщение от модели
        history.append({
            "role": "model",
            "parts": [system_instruction]
        })
        
        # Добавляем историю диалога, если она есть
        if dialog_history:
            for message in dialog_history:
                history.append(message)
        
        return history


# Создаем единственный экземпляр сервиса
gemini_service = GeminiService()
