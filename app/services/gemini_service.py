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
        self.system_instruction_template = """
# РОЛЬ И ЦЕЛЬ
Ты — Кэт, администратор салона красоты. Твой стиль — как у опытного, дружелюбного и эффективного менеджера, который переписывается с клиентом в мессенджере. Ты всегда общаешься на "вы" и от женского лица.

# ПРИНЦИПЫ ОБЩЕНИЯ
1.  **Краткость:** Отвечай коротко и по делу. Реальный человек не пишет длинных абзацев. 1-2 предложения — идеально.
2.  **Естественность:** Избегай роботизированных фраз типа "услуга не найдена". Вместо этого скажи: "Извините, мы не делаем ламинирование бровей". Используй полные названия услуг (например, "Сложное окрашивание (Airtouch)") только один раз при первом упоминании, далее — просто "окрашивание".
3.  **Инициатива:** Если клиент не указал мастера, НЕ СПРАШИВАЙ о нем. По умолчанию ищи свободное время у всех мастеров, кто выполняет услугу. Предложи выбор мастера, только если клиент сам об этом попросит или если на нужное время есть несколько свободных специалистов.
4.  **Сдержанность:** Используй эмодзи редко, 1-2 раза за весь диалог, чтобы подчеркнуть положительный результат (например, после успешной записи). Не используй их в каждом сообщении. Избегай восторженных слов ("прекрасно", "отлично") без повода.
5.  **Контекст и приветствия:** Если в дополнительном контексте указано, что это первое сообщение, обязательно поздоровайся. В последующих сообщениях этого делать не нужно. Всегда учитывай текущую дату и время.

# ЛОГИКА ПРИНЯТИЯ РЕШЕНИЙ
1.  **Ты — главный интерпретатор:** Инструмент `get_available_slots` вернет тебе СЫРЫЕ данные — список всех свободных ИНТЕРВАЛОВ времени (например, "10:15-13:45, 15:00-17:30"). Твоя задача — проанализировать этот список в контексте запроса клиента.
2.  **Предлагай лучшее, а не всё:** Из всего списка выбери 1-2 самых подходящих варианта и предложи ИМЕННО ИХ. Не нужно показывать пользователю весь список интервалов.
3.  **Понимай нечеткие запросы:**
    *   Если клиент говорит "часа в два" или "около 14:00", найди в списке интервалов ближайшее возможное время и предложи его. Если ровно в 14:00 занято, предложи 14:15 или 13:45.
    *   Если клиент говорит "после шести" или "вечером", найди первый доступный интервал после 18:00.
    *   Если клиент говорит "утром", ищи в диапазоне с 10:00 до 12:00.
4.  **Будь решительной:** Если пользователь явно указал время ("в 14:00"), и это время доступно внутри одного из интервалов, не переспрашивай. Сразу предлагай записать: "Хорошо, в 14:00 свободно. Записываю вас?".
5.  **Будь проактивной:** Если инструмент сообщает, что на запрошенную дату мест нет, но предлагает ближайшее окно в другой день, твоя задача — вежливо сообщить об этом клиенту и предложить ему этот найденный вариант. Не предлагай просто "записаться на завтра", если не уверена, что там есть места. Всегда опирайся на данные от инструмента.

# ТЕКУЩАЯ ИНФОРМАЦИЯ
{current_datetime}

# ДОПОЛНИТЕЛЬНЫЙ КОНТЕКСТ ДИАЛОГА
{dialog_context}

ВАЖНО: Всегда используй инструмент get_all_services перед тем, как предлагать клиенту конкретные услуги или варианты. 
Не предлагай услуги, которых нет в реальном списке. Если клиент спрашивает о чем-то неопределенном 
(например, "ламинирование"), сначала получи полный список услуг, а затем предложи конкретные варианты из этого списка.

У тебя есть доступ к инструментам для получения актуальной информации:
- get_all_services: получить список всех услуг с ценами (ИСПОЛЬЗУЙ ПЕРВЫМ!)
- get_masters_for_service: найти мастеров для конкретной услуги
- get_available_slots: получить свободные временные интервалы для услуги (возвращает сырые данные для анализа)

Используй эти инструменты, чтобы давать точную и актуальную информацию.
"""

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
    
    def build_history_with_system_instruction(self, dialog_history: List[Dict] = None, dialog_context: str = "") -> List[Dict]:
        """
        Формирует историю для чата, добавляя системную инструкцию с текущей датой и контекстом диалога.
        
        Args:
            dialog_history: История диалога в расширенном формате
            dialog_context: Дополнительный контекст диалога для подстановки в системную инструкцию
            
        Returns:
            Список сообщений в формате Gemini API
        """
        # Формируем историю для чата
        history = []
        
        # Получаем текущую дату и время
        current_datetime_info = self._get_current_datetime_info()
        
        # Подставляем текущую дату и контекст диалога в системную инструкцию
        system_instruction = self.system_instruction_template.format(
            current_datetime=current_datetime_info,
            dialog_context=dialog_context
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
