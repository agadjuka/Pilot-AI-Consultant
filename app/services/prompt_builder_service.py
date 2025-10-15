"""
Сервис для построения промптов.
Отвечает за формирование всех типов промптов для диалоговой системы.
Реализует трехэтапную архитектуру: Классификация -> Планирование -> Синтез.
"""

from typing import List, Dict, Optional
from datetime import datetime
from app.core.dialogue_pattern_loader import dialogue_patterns
from app.services.tool_definitions import read_only_tools, write_tools


class PromptBuilderService:
    """
    Сервис для построения промптов различных типов.
    Централизует всю логику формирования текстовых инструкций для LLM.
    Реализует трехэтапную архитектуру обработки диалогов.
    """
    
    def __init__(self):
        """
        Инициализирует сервис построения промптов.
        Загружает паттерны диалогов из конфигурации.
        """
        self.dialogue_patterns = dialogue_patterns
        
        # Шаблон для Этапа 1: Классификация
        self.CLASSIFICATION_TEMPLATE = """
Проанализируй историю диалога и новое сообщение. Определи стадию последнего сообщения из списка: {stage_list}.
ВАЖНО: Если клиент жалуется или просит позвать человека, присвой стадию 'conflict_escalation'.

В ответе укажи ТОЛЬКО ID стадии, без дополнительного текста.

## ИСТОРИЯ
{history}

## НОВОЕ СООБЩЕНИЕ
{user_message}

Ответ:"""

        # Шаблон для Этапа 2: Планирование
        self.PLANNING_TEMPLATE = """
# ЗАДАЧА: Спланируй действия для ответа на запрос клиента на стадии '{stage_name}'.
# КОНТЕКСТ:
- Текущая дата: {current_datetime}
- История: {history}
- Запрос: {user_message}

# РЕКОМЕНДАЦИИ ДЛЯ ЭТОЙ СТАДИИ:
{stage_principles}

# ДОСТУПНЫЕ ИНСТРУМЕНТЫ (только для сбора информации):
{read_only_tools_summary}

# ТВОЯ ЗАДАЧА:
Следуя рекомендациям, выбери инструменты для сбора данных. Ответь ТОЛЬКО JSON-ом `{{"tool_calls": [...]}}`.
"""

        # Шаблон для Этапа 3: Синтез
        self.SYNTHESIS_TEMPLATE = """
# РОЛЬ: Ты — Кэт, AI-администратор салона красоты "Элегант". Ты дружелюбная, профессиональная и всегда готова помочь клиентам с записью на услуги.

# ГЛАВНАЯ ЗАДАЧА: Логично продолжи диалог, основываясь на всем контексте. Не здоровайся, если это уже было.

# КОНТЕКСТ:
- Текущая дата: {current_datetime}
- О клиенте: {client_context}
- История: {history}
- Последний запрос: {user_message}
- Собранные тобой данные: {tool_results}

# РЕКОМЕНДАЦИИ ПО СТИЛЮ (для стадии: {stage_name}):
{stage_principles}

# ВОЗМОЖНЫЕ ДЕЙСТВИЯ:
{write_tools_summary}

# ФОРМАТ ДЕЙСТВИЯ:
Если нужно выполнить действие, начни ответ с JSON-блока ```json {{"tool_calls": [...]}} ```, а затем напиши текст для клиента.

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
        
        # Получаем список стадий из dialogue_patterns
        stage_list = ", ".join(self.dialogue_patterns.keys())
        
        # Собираем промпт по шаблону
        prompt = self.CLASSIFICATION_TEMPLATE.format(
            stage_list=stage_list,
            history=history_text,
            user_message=user_message
        )
        
        return prompt
    
    def build_planning_prompt(
        self, 
        stage_name: str,
        history: List[Dict], 
        user_message: str
    ) -> str:
        """
        Формирует промпт для Этапа 2: Планирование инструментов.
        Использует только read_only_tools (разведывательные инструменты).
        
        Args:
            stage_name: Определенная стадия диалога
            history: История диалога
            user_message: Новое сообщение пользователя
            
        Returns:
            Промпт для планирования
        """
        # Получаем данные стадии из dialogue_patterns.json
        stage_data = self.dialogue_patterns.get(stage_name, {})
        stage_principles = self._format_principles(stage_data.get('principles', []))
        
        # Генерируем краткое описание только read-only инструментов
        read_only_tools_summary = self._generate_tools_summary(read_only_tools)
        
        # Генерируем текущую дату и время
        current_datetime = self._generate_current_datetime()
        
        # Форматируем историю диалога
        history_text = self._format_dialog_history(history)
        
        # Собираем промпт по шаблону
        prompt = self.PLANNING_TEMPLATE.format(
            stage_name=stage_name,
            stage_principles=stage_principles,
            read_only_tools_summary=read_only_tools_summary,
            current_datetime=current_datetime,
            history=history_text,
            user_message=user_message
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
        Формирует промпт для Этапа 3: Синтез финального ответа.
        Использует write_tools (исполнительные инструменты) для возможных действий.
        
        Args:
            stage_name: Определенная стадия диалога
            history: История диалога
            user_message: Новое сообщение пользователя
            tool_results: Результаты выполнения инструментов
            client_name: Имя клиента
            client_phone_saved: Сохранен ли телефон клиента
            
        Returns:
            Промпт для синтеза ответа
        """
        # Получаем данные стадии из dialogue_patterns.json
        stage_data = self.dialogue_patterns.get(stage_name, {})
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
        prompt = self.SYNTHESIS_TEMPLATE.format(
            current_datetime=current_datetime,
            client_context=client_context,
            history=history_text,
            user_message=user_message,
            tool_results=tool_results,
            stage_name=stage_name,
            stage_principles=stage_principles,
            write_tools_summary=write_tools_summary
        )
        
        return prompt