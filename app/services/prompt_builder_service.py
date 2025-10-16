"""
Сервис для построения промптов.
Отвечает за формирование всех типов промптов для диалоговой системы.
Реализует финальную трехэтапную архитектуру: Классификация -> Мышление -> Синтез.
"""

from typing import List, Dict, Optional
from datetime import datetime
from app.core.dialogue_pattern_loader import dialogue_patterns


class PromptBuilderService:
    """
    Сервис для построения промптов различных типов.
    Централизует всю логику формирования текстовых инструкций для LLM.
    Реализует финальную трехэтапную архитектуру обработки диалогов.
    """
    
    def __init__(self):
        """
        Инициализирует сервис построения промптов.
        Загружает паттерны диалогов из конфигурации.
        """
        self.dialogue_patterns = dialogue_patterns
        
        # === ЭТАП 1: КЛАССИФИКАЦИЯ ===
        self.CLASSIFICATION_TEMPLATE = """
# ЗАДАЧА
Определи стадию ПОСЛЕДНЕГО сообщения клиента, выбрав ОДНУ из списка ниже.

---

# СПИСОК СТАДИЙ И ИХ ОПИСАНИЯ
- `greeting`: Клиент просто здоровается.
- `service_inquiry`: Клиент спрашивает об услугах, их деталях или ценах.
- `booking_start`: Клиент выразил желание записаться, но еще не назвал дату.
- `availability_check`: Клиент назвал дату/день недели и хочет узнать свободное время.
- `booking_confirmation`: Клиент выбрал и подтвердил конкретное время.
- `view_booking`: Клиент хочет посмотреть свои записи.
- `cancellation_request`: Клиент хочет отменить запись.
- `conflict_escalation`: Клиент жалуется или просит позвать менеджера (ВЫСШИЙ ПРИОРИТЕТ).
- `fallback`: Сообщение не подходит ни под одну из категорий.

---

# КОНТЕКСТ ДИАЛОГА
## ИСТОРИЯ:
{history}

## НОВОЕ СООБЩЕНИЕ:
{user_message}

---

# ФОРМАТ ОТВЕТА
В ответе укажи ТОЛЬКО ID стадии.
"""

        # === ЭТАП 2: МЫШЛЕНИЕ ===
        self.THINKING_TEMPLATE = """
# ЗАДАЧА
Ты — Кэт, AI-администратор салона красоты "Элегант". Твоя задача — логично продолжить диалог, используя собранные данные.
Твоя задача — логично продолжить диалог, проанализировав историю и запрос клиента.

# СЦЕНАРИЙ ДЛЯ СТАДИИ
{stage_scenario}

# ДОСТУПНЫЕ ИНСТРУМЕНТЫ
{thinking_tools}

# ОБЩИЕ ПРАВИЛА
{rules}

# КОНТЕКСТ
- Текущая дата: {current_datetime}
- О клиенте: {client_context}
- История: {history}
- Запрос: {user_message}
{hidden_context}

# ФОРМАТ ЗАПРОСА ДАННЫХ (если нужен)
Если тебе нужны данные от инструмента, твой ответ должен содержать ОДНУ или НЕСКОЛЬКО строк в следующем формате:
`TOOL_CALL: имя_инструмента(параметр1="значение1", параметр2="значение2")`

**ПРИМЕР 1 (один инструмент):**
`TOOL_CALL: get_available_slots(date="2025-10-16", service_name="маникюр")`

**ПРИМЕР 2 (несколько инструментов):**
`TOOL_CALL: get_all_services()`
`TOOL_CALL: get_available_slots(date="2025-10-16")`

Твой ответ должен содержать ТОЛЬКО эти строки, без дополнительного текста.
Если инструменты не нужны, сформулируй текстовый ответ для клиента.
"""

        # === ЭТАП 3: СИНТЕЗ ===
        self.SYNTHESIS_TEMPLATE = """
# РОЛЬ И ЗАДАЧА
Ты — Кэт, AI-администратор салона красоты "Элегант". Твоя задача — логично продолжить диалог, используя собранные данные.

# СЦЕНАРИЙ ДЕЙСТВИЙ
{stage_scenario}

# ВОЗМОЖНЫЕ ДЕЙСТВИЯ
{synthesis_tools}

# ОБЩИЕ ПРАВИЛА
{rules}

# КОНТЕКСТ
- Текущая дата: {current_datetime}
- О клиенте: {client_context}
- История: {history}
- Последний запрос: {user_message}
- Собранные данные: {tool_results}

# ФОРМАТ ОТВЕТА
Если нужны инструменты + ответ клиенту — сначала верни строки TOOL_CALL, а затем текст ответа.
Если инструменты не нужны — верни только текст ответа.

**ПРИМЕР ГИБРИДНОГО ОТВЕТА:**
`TOOL_CALL: create_appointment(date="2025-10-16", time="15:00", service_name="маникюр")`
`TOOL_CALL: send_confirmation_sms(phone="+7900123456")`

Отлично! Я записала вас на маникюр на завтра в 15:00. Подтверждение придет на ваш телефон.
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
        Использует структурированный формат с четкими разделителями ролей.
        
        Args:
            history: Список сообщений диалога
            
        Returns:
            Отформатированная строка с историей диалога
        """
        if not history:
            return "История диалога пуста"
        
        formatted_history = []
        for msg in history:
            role_tag = "<|user|>" if msg["role"] == "user" else "<|assistant|>"
            content = msg["parts"][0]["text"]
            formatted_history.append(f"{role_tag}\n{content}")
        
        return "\n".join(formatted_history)
    
    # === МЕТОДЫ ДЛЯ ТРЕХЭТАПНОЙ АРХИТЕКТУРЫ ===
    
    def build_classification_prompt(
        self, 
        history: List[Dict], 
        user_message: str
    ) -> str:
        """
        Формирует промпт для Этапа 1: Классификация стадии диалога.
        
        Args:
            history: История диалога
            user_message: Новое сообщение пользователя
            
        Returns:
            Промпт для классификации
        """
        # Форматируем историю диалога
        history_text = self._format_dialog_history(history)
        
        # Собираем промпт по шаблону
        prompt = self.CLASSIFICATION_TEMPLATE.format(
            history=history_text,
            user_message=user_message
        )
        
        return prompt
    
    def build_thinking_prompt(
        self,
        stage_name: str,
        history: List[Dict],
        user_message: str,
        client_name: Optional[str] = None,
        client_phone_saved: bool = False,
        hidden_context: str = ""
    ) -> str:
        """
        Формирует промпт для Этапа 2: Мышление.
        
        Args:
            stage_name: Определенная стадия диалога
            history: История диалога
            user_message: Новое сообщение пользователя
            client_name: Имя клиента
            client_phone_saved: Сохранен ли телефон клиента
            hidden_context: Скрытый контекст
            
        Returns:
            Промпт для этапа мышления
        """
        # Получаем данные стадии из dialogue_patterns
        stage_data = self.dialogue_patterns.get(stage_name, {})
        
        # Форматируем историю диалога
        history_text = self._format_dialog_history(history)
        
        # Формируем контекст клиента
        client_context_parts = []
        if client_name:
            client_context_parts.append(f"Имя: {client_name}")
        if client_phone_saved:
            client_context_parts.append("Телефон: сохранен в базе")
        
        client_context = ", ".join(client_context_parts) if client_context_parts else "Данные клиента не известны"
        
        # Генерируем текущую дату и время
        current_datetime = self._generate_current_datetime()
        
        # Форматируем сценарий стадии
        scenario = stage_data.get('scenario', [])
        stage_scenario = "\n".join(scenario) if scenario else "Будь вежливым, профессиональным и полезным."
        
        # Получаем инструменты и правила из конфигурации
        thinking_tools = stage_data.get('thinking_tools', '')
        rules = stage_data.get('rules', '')
        
        # Собираем промпт по шаблону
        prompt = self.THINKING_TEMPLATE.format(
            current_datetime=current_datetime,
            client_context=client_context,
            history=history_text,
            user_message=user_message,
            hidden_context=hidden_context,
            stage_scenario=stage_scenario,
            thinking_tools=thinking_tools,
            rules=rules
        )
        
        return prompt
    
    def build_synthesis_prompt(
        self,
        stage_name: str,
        history: List[Dict],
        user_message: str,
        tool_results: str,
        client_name: Optional[str] = None,
        client_phone_saved: bool = False
    ) -> str:
        """
        Формирует промпт для Этапа 3: Синтез.
        
        Args:
            stage_name: Определенная стадия диалога
            history: История диалога
            user_message: Новое сообщение пользователя
            tool_results: Результаты выполнения инструментов с этапа мышления
            client_name: Имя клиента
            client_phone_saved: Сохранен ли телефон клиента
            
        Returns:
            Промпт для этапа синтеза
        """
        # Получаем данные стадии из dialogue_patterns
        stage_data = self.dialogue_patterns.get(stage_name, {})
        
        # Форматируем историю диалога
        history_text = self._format_dialog_history(history)
        
        # Формируем контекст клиента
        client_context_parts = []
        if client_name:
            client_context_parts.append(f"Имя: {client_name}")
        if client_phone_saved:
            client_context_parts.append("Телефон: сохранен в базе")
        
        client_context = ", ".join(client_context_parts) if client_context_parts else "Данные клиента не известны"
        
        # Генерируем текущую дату и время
        current_datetime = self._generate_current_datetime()
        
        # Форматируем сценарий стадии
        scenario = stage_data.get('scenario', [])
        stage_scenario = "\n".join(scenario) if scenario else "Будь вежливым, профессиональным и полезным."
        
        # Получаем инструменты и правила из конфигурации
        synthesis_tools = stage_data.get('synthesis_tools', '')
        rules = stage_data.get('rules', '')
        
        # Собираем промпт по шаблону
        prompt = self.SYNTHESIS_TEMPLATE.format(
            current_datetime=current_datetime,
            client_context=client_context,
            history=history_text,
            user_message=user_message,
            tool_results=tool_results,
            stage_scenario=stage_scenario,
            synthesis_tools=synthesis_tools,
            rules=rules
        )
        
        return prompt