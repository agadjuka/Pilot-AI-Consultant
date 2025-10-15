"""
Сервис для построения промптов.
Отвечает за формирование всех типов промптов для диалоговой системы.
Реализует двухтактную архитектуру: Планирование -> Синтез.
"""

from typing import List, Dict, Optional
from datetime import datetime
from app.core.dialogue_pattern_loader import dialogue_patterns
from app.services.tool_definitions import salon_tools


class PromptBuilderService:
    """
    Сервис для построения промптов различных типов.
    Централизует всю логику формирования текстовых инструкций для LLM.
    Реализует двухтактную архитектуру обработки диалогов.
    """
    
    def __init__(self):
        """
        Инициализирует сервис построения промптов.
        Загружает паттерны диалогов из конфигурации.
        """
        self.dialogue_patterns = dialogue_patterns
        
        # Шаблон для Этапа 1: Планирование
        self.planning_template = """
# ЗАДАЧА
Ты — умный планировщик для AI-ассистента. Твоя задача — проанализировать диалог и выполнить три действия:
1.  **Продолжи диалог логично:** Учти предыдущие сообщения, чтобы не повторяться и не здороваться снова.
2.  **Определи стадию** последнего сообщения из списка: `{stage_list}`.
3.  **Спланируй действия:** Следуя ЦЕЛИ для этой стадии, выбери инструменты для сбора информации.

# ЦЕЛИ ПО СТАДИЯМ (Что нужно сделать)
- `greeting`: Инструменты не нужны, просто вежливо ответь.
- `service_inquiry`: Узнай детали об услуге (цена, длительность), используя `get_all_services`.
- `price_inquiry`: Найди цену услуги, используя `get_all_services`.
- `availability_check`: Найди свободное время, используя `get_available_slots`. Убедись, что услуга известна из контекста.
- `booking_confirmation`: Проверь наличие всех данных и вызови `create_appointment`.
- `view_booking`: Получи список записей клиента, используя `get_my_appointments`.
- `cancellation_request`: Отмени запись, используя `cancel_appointment_by_id`.
- `rescheduling`: Перенеси запись, используя `reschedule_appointment_by_id`.
- `handle_issue` / `conflict_escalation`: Вызови `call_manager`.
- `fallback`: Инструменты не нужны, вежливо ответь по ситуации.

# ТЕКУЩАЯ ДАТА (для преобразования "завтра", "в субботу" и т.д.)
{current_datetime}

# ИНСТРУМЕНТЫ (Что ты можешь сделать)
{tools_summary}

# ИСТОРИЯ ДИАЛОГА
{history}

# НОВОЕ СООБЩЕНИЕ КЛИЕНТА
{user_message}

# ФОРМАТ ОТВЕТА
Ответь ТОЛЬКО в формате JSON с ключами 'stage' и 'tool_calls'.
- 'stage': строка с названием стадии.
- 'tool_calls': JSON-массив, где КАЖДЫЙ элемент — это СЛОВАРЬ с ключами 'tool_name' и 'parameters'.
  - 'tool_name': имя инструмента (строка).
  - 'parameters': словарь с параметрами. Если у инструмента нет параметров, передай пустой словарь {{}}.

ПРИМЕР 1 (с параметрами):
{{"stage": "availability_check", "tool_calls": [{{"tool_name": "get_available_slots", "parameters": {{"date": "2025-10-16"}}}}]}}

ПРИМЕР 2 (без параметров):
{{"stage": "service_inquiry", "tool_calls": [{{"tool_name": "get_all_services", "parameters": {{}}}}]}}

ВАЖНО: Твой ответ должен быть ТОЛЬКО валидным JSON без дополнительного текста!
"""

        # Шаблон для Этапа 2: Синтез ответа
        self.synthesis_template = """
# РОЛЬ И СТИЛЬ
Ты — Кэт, дружелюбный и профессиональный AI-администратор салона красоты. Общайся на "вы", кратко, по-человечески. Используй эмодзи сдержанно.

# ИСТОРИЯ ДИАЛОГА
{history}

# ЗАПРОС КЛИЕНТА
{user_message}

# ДАННЫЕ, КОТОРЫЕ ТЫ ЗАПРОСИЛ(А) У СИСТЕМЫ
{tool_results}

# РЕКОМЕНДАЦИИ ПО СТИЛЮ (для текущей ситуации)
{stage_principles}

# ТВОЯ ЗАДАЧА
Твоя задача — **логично продолжить диалог** с клиентом. Проанализируй ИСТОРИЮ ДИАЛОГА, чтобы понять контекст и не повторяться. Используй ПОЛУЧЕННЫЕ ДАННЫЕ, чтобы дать исчерпывающий ответ на ПОСЛЕДНИЙ ЗАПРОС КЛИЕНТА. Твой ответ должен соответствовать твоей РОЛИ и РЕКОМЕНДАЦИЯМ ПО СТИЛЮ.
"""
    
    def _generate_current_datetime(self) -> str:
        """
        Генерирует строку с текущей датой и временем для контекста LLM.
        
        Returns:
            Строка с текущей датой и временем в читаемом формате
        """
        now = datetime.now()
        
        # Русские названия дней недели
        weekdays = {
            0: "Понедельник",
            1: "Вторник", 
            2: "Среда",
            3: "Четверг",
            4: "Пятница",
            5: "Суббота",
            6: "Воскресенье"
        }
        
        weekday = weekdays[now.weekday()]
        date_str = now.strftime("%d.%m.%Y")
        time_str = now.strftime("%H:%M")
        
        return f"Сегодня: {weekday}, {date_str}, время: {time_str}"
    
    def _format_dialog_history(self, history: List[Dict]) -> str:
        """
        Форматирует историю диалога в читаемую строку для LLM.
        
        Args:
            history: Список сообщений диалога
            
        Returns:
            Отформатированная строка с историей диалога
        """
        if not history:
            return "История диалога пуста"
        
        formatted_history = []
        for msg in history:
            role = "Пользователь" if msg["role"] == "user" else "Ассистент"
            content = msg["parts"][0]["text"]
            formatted_history.append(f"{role}: {content}")
        
        return "\n".join(formatted_history)
    
    def _generate_tools_summary(self) -> str:
        """
        Генерирует краткое описание всех доступных инструментов.
        
        Returns:
            Отформатированная строка с описанием инструментов
        """
        tools_summary = ""
        
        for func_decl in salon_tools.function_declarations:
            # Извлекаем параметры из схемы
            params = []
            if hasattr(func_decl, 'parameters') and func_decl.parameters:
                # Преобразуем в словарь для работы
                params_dict = func_decl.parameters
                if hasattr(params_dict, 'properties') and params_dict.properties:
                    params = list(params_dict.properties.keys())
            
            # Формируем краткое описание
            if params:
                params_str = ", ".join(params)
                # Берем только первое предложение из описания
                short_desc = func_decl.description.split('.')[0]
                tools_summary += f"- {func_decl.name}({params_str}): {short_desc}.\n"
            else:
                # Берем только первое предложение из описания
                short_desc = func_decl.description.split('.')[0]
                tools_summary += f"- {func_decl.name}(): {short_desc}.\n"
        
        return tools_summary.strip()
    
    def _format_principles(self, principles: List[str], client_name: Optional[str] = None, client_phone_saved: bool = False) -> str:
        """
        Форматирует принципы стадии в читаемую строку.
        
        Args:
            principles: Список принципов из dialogue_patterns.json
            client_name: Имя клиента
            client_phone_saved: Сохранен ли телефон клиента
            
        Returns:
            Отформатированная строка с принципами
        """
        if not principles:
            return "Будь вежливым, профессиональным и полезным. Всегда предоставляй точную информацию."
        
        # Добавляем информацию о клиенте, если она есть
        client_info = ""
        if client_name:
            client_info += f" Имя клиента: {client_name}."
        if client_phone_saved:
            client_info += " Телефон клиента сохранен в базе данных."
        
        # Форматируем принципы в список
        formatted_principles = []
        for principle in principles:
            formatted_principles.append(f"- {principle}")
        
        result = "\n".join(formatted_principles)
        if client_info:
            result += f"\n\nДополнительная информация:{client_info}"
        
        return result
    
    def build_planning_prompt(
        self, 
        history: List[Dict], 
        user_message: str
    ) -> str:
        """
        Формирует промпт для Этапа 1: Планирование.
        
        Args:
            history: История диалога
            user_message: Новое сообщение пользователя
            
        Returns:
            Промпт для планирования
        """
        # Генерируем краткое описание инструментов
        tools_summary = self._generate_tools_summary()
        
        # Генерируем текущую дату и время
        current_datetime = self._generate_current_datetime()
        
        # Форматируем историю диалога
        history_text = self._format_dialog_history(history)
        
        # Получаем список стадий из dialogue_patterns
        stage_list = ", ".join(self.dialogue_patterns.keys())
        
        # Собираем промпт по шаблону
        prompt = self.planning_template.format(
            stage_list=stage_list,
            tools_summary=tools_summary,
            current_datetime=current_datetime,
            history=history_text,
            user_message=user_message
        )
        
        return prompt
    
    def build_synthesis_prompt(
        self, 
        history: List[Dict],
        user_message: str,
        tool_results: str,
        stage: str,
        client_name: Optional[str] = None,
        client_phone_saved: bool = False
    ) -> str:
        """
        Формирует промпт для Этапа 2: Синтез финального ответа.
        
        Args:
            history: История диалога
            user_message: Новое сообщение пользователя
            tool_results: Результаты выполнения инструментов
            stage: ID стадии диалога
            client_name: Имя клиента
            client_phone_saved: Сохранен ли телефон клиента
            
        Returns:
            Промпт для синтеза ответа
        """
        # Получаем данные стадии из dialogue_patterns.json
        stage_data = self.dialogue_patterns.get(stage, {})
        stage_principles = self._format_principles(stage_data.get('principles', []), client_name, client_phone_saved)
        
        # Форматируем историю диалога
        history_text = self._format_dialog_history(history)
        
        # Собираем промпт по шаблону
        prompt = self.synthesis_template.format(
            history=history_text,
            user_message=user_message,
            tool_results=tool_results,
            stage_principles=stage_principles
        )
        
        return prompt