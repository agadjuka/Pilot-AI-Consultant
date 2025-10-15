"""
Сервис для построения промптов.
Отвечает за формирование всех типов промптов для диалоговой системы.
Реализует двухтактную архитектуру: Планирование -> Синтез.
"""

from typing import List, Dict, Optional
from datetime import datetime
from app.core.dialogue_pattern_loader import dialogue_patterns
from app.services.tool_definitions import read_only_tools, write_tools


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
# РОЛЬ: Ты — умный планировщик для AI-ассистента салона красоты.

# ГЛАВНАЯ ЗАДАЧА:
Проанализируй **НОВОЕ СООБЩЕНИЕ КЛИЕНТА** в контексте **ИСТОРИИ ДИАЛОГА**. Твоя цель — определить `stage` (стадию) диалога и спланировать `tool_calls` (вызовы инструментов), необходимые для сбора информации.

## КОНТЕКСТ
- **Текущая дата:** {current_datetime}
- **История диалога:**
{history}
- **Новое сообщение клиента:** {user_message}

## ИНСТРУКЦИИ ПО ПЛАНИРОВАНИЮ
1.  **Определи стадию:** Выбери одну из: `{stage_list}`.
2.  **Следуй цели стадии:** Для выбранной стадии выполни соответствующую цель.
3.  **Используй историю:** Если для инструмента нужен параметр (например, `service_name`), а в новом сообщении его нет, найди его в истории.

## ЦЕЛИ ПО СТАДИЯМ
- `greeting`: Инструменты не нужны.
- `service_inquiry`: Цель — предоставить информацию о запрошенной услуге и начать диалог о записи. Используй `get_all_services`, чтобы найти цену/длительность. НЕ ИСПОЛЬЗУЙ `get_available_slots`, пока клиент явно не назовет дату (сегодня, завтра, в субботу и т.д.).
- `price_inquiry`: Цель — ответить о цене. Используй `get_all_services`.
- `availability_check`: Цель — найти свободное время. Используй `get_available_slots`. Услуга и дата должны быть известны из контекста.
- `booking_confirmation`: Цель — подготовиться к записи. Убедись, что все данные согласованы. Инструменты на этом этапе не вызывай.
- `view_booking`: Цель — показать записи. Используй `get_my_appointments`.
- `cancellation_request` / `rescheduling`: Цель — начать отмену/перенос. Используй `get_my_appointments`, чтобы понять, с чем работать.
- `handle_issue` / `conflict_escalation`: Цель — позвать человека. Используй `call_manager`.
- `fallback`: Инструменты не нужны.

## ДОСТУПНЫЕ ИНСТРУМЕНТЫ
{tools_summary}

{hidden_context}

# ФОРМАТ ОТВЕТА
Ответь ТОЛЬКО валидным JSON с ключами 'stage' и 'tool_calls'. `tool_calls` — это массив объектов `{{"tool_name": "...", "parameters": {{...}}}}`.
"""

        # Шаблон для Этапа 2: Синтез ответа
        self.synthesis_template = """
# РОЛЬ: Ты — Кэт, AI-администратор салона красоты.

# ГЛАВНАЯ ЗАДАЧА:
Твоя задача — **логично продолжить диалог**. Проанализируй **ИСТОРИЮ ДИАЛОГА** и убедись, что твой ответ является ее естественным продолжением. **Не здоровайся**, если приветствие уже было.

## КОНТЕКСТ
- **Текущая дата:** {current_datetime}
- **О клиенте:** {client_context}
- **История диалога:**
{history}
- **Последний запрос клиента:** {user_message}
- **Собранные тобой данные:**
{tool_results}

## РЕКОМЕНДАЦИИ ПО СТИЛЮ (для стадии: {stage_name})
{stage_principles}

## ВОЗМОЖНЫЕ ДЕЙСТВИЯ
Если твой ответ подразумевает действие, начни его с JSON-блока с вызовом инструмента.
{write_tools_summary}

# ФОРМАТ ВЫПОЛНЕНИЯ ДЕЙСТВИЯ
Если ты решил(а) выполнить действие, твой ответ ДОЛЖЕН начинаться со **строго** отформатированного JSON-блока. После блока напиши текст для клиента.

**СТРОГИЙ ФОРМАТ:**
```json
{{
  "tool_calls": [
    {{
      "tool_name": "имя_инструмента",
      "parameters": {{
        "имя_параметра": "значение"
      }}
    }}
  ]
}}
```

# ФИНАЛЬНЫЙ ОТВЕТ:
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
    
    def _generate_tools_summary(self, tools_list: List) -> str:
        """
        Генерирует краткое описание указанного набора инструментов.
        
        Args:
            tools_list: Список FunctionDeclaration объектов
            
        Returns:
            Отформатированная строка с описанием инструментов
        """
        tools_summary = ""
        
        for func_decl in tools_list:
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
        user_message: str,
        hidden_context: str = ""
    ) -> str:
        """
        Формирует промпт для Этапа 1: Планирование.
        Использует только read_only_tools (разведывательные инструменты).
        
        Args:
            history: История диалога
            user_message: Новое сообщение пользователя
            hidden_context: Скрытый контекст с записями (для отмены/переноса)
            
        Returns:
            Промпт для планирования
        """
        # Генерируем краткое описание только read-only инструментов
        tools_summary = self._generate_tools_summary(read_only_tools)
        
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
            hidden_context=hidden_context,
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
        Использует write_tools (исполнительные инструменты) для возможных действий.
        
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
        
        # Формируем контекст клиента
        client_context_parts = []
        if client_name:
            client_context_parts.append(f"Имя: {client_name}")
        if client_phone_saved:
            client_context_parts.append("Телефон: сохранен в базе")
        
        client_context = ", ".join(client_context_parts) if client_context_parts else "Данные клиента не известны"
        
        # Генерируем краткое описание write_tools (исполнительных инструментов)
        write_tools_summary = self._generate_tools_summary(write_tools)
        
        # Генерируем текущую дату и время
        current_datetime = self._generate_current_datetime()
        
        # Собираем промпт по шаблону
        prompt = self.synthesis_template.format(
            current_datetime=current_datetime,
            history=history_text,
            user_message=user_message,
            tool_results=tool_results,
            client_context=client_context,
            stage_name=stage,
            stage_principles=stage_principles,
            write_tools_summary=write_tools_summary
        )
        
        return prompt