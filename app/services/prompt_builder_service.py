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
Ты — умный планировщик для AI-ассистента салона красоты. Твоя задача — проанализировать запрос клиента и историю диалога, чтобы решить, какие инструменты нужно вызвать для сбора ВСЕЙ необходимой информации для полного ответа.

# ПРАВИЛА
- Если для ответа нужна информация (цена, свободное время, список услуг и т.д.), ты ДОЛЖЕН выбрать один или несколько инструментов.
- Если информация не нужна (например, на простое "спасибо"), верни пустой список инструментов.
- Думай на шаг вперед. Если клиент хочет записаться, ему, вероятно, понадобится и информация об услуге, и свободное время.

# ИНСТРУМЕНТЫ (твой API)
{tools_summary}

# ТЕКУЩАЯ ДАТА
{current_datetime}

# ИСТОРИЯ ДИАЛОГА
{history}

# НОВОЕ СООБЩЕНИЕ КЛИЕНТА
{user_message}

# ФОРМАТ ОТВЕТА
Ответь ТОЛЬКО JSON-массивом с вызовами инструментов. Никакого другого текста.
Пример: `[{{"tool_name": "get_available_slots", "parameters": {{"service_name": "маникюр"}}}}]`
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
Основываясь на своей роли, полученных данных и рекомендациях по стилю, сформулируй финальный, вежливый и исчерпывающий ответ для клиента.
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
        
        # Собираем промпт по шаблону
        prompt = self.planning_template.format(
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