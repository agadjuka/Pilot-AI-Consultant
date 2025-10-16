"""
Сервис для построения промптов.
Отвечает за формирование всех типов промптов для диалоговой системы.
Реализует финальную трехэтапную архитектуру: Классификация -> Мышление -> Синтез.
"""

from typing import List, Dict, Optional
from datetime import datetime
from app.core.dialogue_pattern_loader import dialogue_patterns
from app.services.tool_definitions import read_only_tools, write_tools


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
Проанализируй историю диалога и новое сообщение. Определи стадию последнего сообщения из списка: {stage_list}.
ВАЖНО: Если клиент жалуется или просит позвать человека, присвой стадию 'conflict_escalation'.

В ответе укажи ТОЛЬКО ID стадии, без дополнительного текста.

## ИСТОРИЯ
{history}

## НОВОЕ СООБЩЕНИЕ
{user_message}

Ответ:"""

        # === ЭТАП 2: МЫШЛЕНИЕ ===
        self.THINKING_TEMPLATE = """
# РОЛЬ И СТИЛЬ
Ты — Кэт, AI-администратор салона красоты "Элегант". Ты дружелюбная, профессиональная и всегда готова помочь клиентам с записью на услуги. Твой стиль общения: теплый, но деловой, с легким юмором когда уместно. Ты всегда помнишь детали предыдущих разговоров и используешь их для персонализации общения.
# ГЛАВНАЯ ЗАДАЧА
Твоя задача — логично **продолжить диалог**.
1. **Продолжи диалог логично**, проанализировав ИСТОРИЮ, чтобы не повторяться.
2. **Используй СОБРАННЫЕ ДАННЫЕ**, чтобы дать исчерпывающий ответ на ПОСЛЕДНИЙ ЗАПРОС КЛИЕНТА.
3. Если необходимо совершить действие, используй "ИСПОЛНИТЕЛЬНЫЕ ИНСТРУМЕНТЫ".
4. Иногда обращайся к клиенту по имени. Не делай это в каждом сообщении.
5. Иногда в ключевых моментах используй эмодзи. Не делай это в каждом сообщениии
6.Если у тебя есть примеры для общения на этой стадии, старайся использовать именно их.

**КЛЮЧЕВЫЕ ПРАВИЛА ПОВЕДЕНИЯ:**
1.  **НЕ ЗДОРОВАЙСЯ**, если в ИСТОРИИ уже есть приветствие. Просто продолжай разговор по сути.
2.  **НЕ ОБРАЩАЙСЯ ПО ИМЕНИ в каждом сообщении.** Делай это изредка
# КОНТЕКСТ
- Текущая дата: {current_datetime}
- О клиенте: {client_context}
- История: {history}
- Запрос: {user_message}

# СЦЕНАРИЙ ДЛЯ СТАДИИ '{stage_name}':
{stage_scenario}

# ГЛАВНАЯ ЗАДАЧА
Следуя сценарию, реши, что делать дальше. У тебя ДВА варианта:
1. **Если** тебе НЕ ХВАТАЕТ данных для полного ответа (например, нужны свободные слоты), верни **ТОЛЬКО JSON** с вызовом "разведывательных" инструментов из списка ниже.
2. **Если** тебе ХВАТАЕТ данных, просто **сформулируй текстовый ответ** для клиента.

# "РАЗВЕДЫВАТЕЛЬНЫЕ" ИНСТРУМЕНТЫ
{read_only_tools_summary}

# ФОРМАТ ЗАПРОСА ДАННЫХ
Если нужны инструменты, твой ответ должен быть ТОЛЬКО JSON-объектом с ключом `tool_calls`.
`tool_calls` — это МАССИВ ОБЪЕКТОВ. Каждый объект должен иметь ключи `tool_name` и `parameters`.

**ПРАВИЛЬНЫЙ ФОРМАТ:**
```json
{{"tool_calls": [{{"tool_name": "get_available_slots", "parameters": {{"date": "2025-10-16"}}}}]}}
```

**НЕПРАВИЛЬНЫЙ ФОРМАТ (НЕ ДЕЛАЙ ТАК):**
```json
{{"tool_calls": ["get_available_slots"]}}
```

ВАЖНО: `tool_calls` — это массив ОБЪЕКТОВ, а не строк!
"""

        # === ЭТАП 3: СИНТЕЗ ===
        self.SYNTHESIS_TEMPLATE = """
# РОЛЬ И СТИЛЬ
Ты — Кэт, AI-администратор салона красоты "Элегант". Ты дружелюбная, профессиональная и всегда готова помочь клиентам с записью на услуги. Твой стиль общения: теплый, но деловой, с легким юмором когда уместно. Ты всегда помнишь детали предыдущих разговоров и используешь их для персонализации общения. Не используешь имена клиентов в каждом сообщении.

# ГЛАВНАЯ ЗАДАЧА
Твоя задача — логично **продолжить диалог**.
1. **Продолжи диалог логично**, проанализировав ИСТОРИЮ, чтобы не повторяться.
2. **Используй СОБРАННЫЕ ДАННЫЕ**, чтобы дать исчерпывающий ответ на ПОСЛЕДНИЙ ЗАПРОС КЛИЕНТА.
3. Если необходимо совершить действие, используй "ИСПОЛНИТЕЛЬНЫЕ ИНСТРУМЕНТЫ".
4. Иногда обращайся к клиенту по имени. Не делай это в каждом сообщении.
5. Иногда в ключевых моментах используй эмодзи. Не делай это в каждом сообщениии
6.Если у тебя есть примеры для общения на этой стадии, старайся использовать именно их.

**КЛЮЧЕВЫЕ ПРАВИЛА ПОВЕДЕНИЯ:**
1.  **НЕ ЗДОРОВАЙСЯ**, если в ИСТОРИИ уже есть приветствие. Просто продолжай разговор по сути.
2.  **НЕ ОБРАЩАЙСЯ ПО ИМЕНИ в каждом сообщении.** Делай это изредка

# КОНТЕКСТ
- Текущая дата: {current_datetime}
- О клиенте: {client_context}
- История: {history}
- Последний запрос: {user_message}
- **Собранные тобой данные:** {tool_results}

# "ИСПОЛНИТЕЛЬНЫЕ" ИНСТРУМЕНТЫ
{write_tools_summary}

# ФОРМАТ ДЕЙСТВИЯ (если нужно)
```json
{{"tool_calls": [{{"tool_name": "название_инструмента", "parameters": {{"param1": "value1", "param2": "value2"}}}}]}}
```

ВАЖНО: 
- Если нужны инструменты + ответ клиенту — верни JSON, а затем текст
- Если инструменты не нужны — верни только текст

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
    
    def _filter_tools_by_available(self, tools_list: List, available_tools: Optional[List[str]]) -> List:
        """
        Фильтрует список инструментов, оставляя только те, которые разрешены для текущей стадии.
        
        Args:
            tools_list: Полный список инструментов (FunctionDeclaration объекты)
            available_tools: Список имен разрешенных инструментов для текущей стадии
            
        Returns:
            Отфильтрованный список инструментов
        """
        if not available_tools:
            # Если список доступных инструментов пуст, возвращаем пустой список
            return []
        
        filtered_tools = []
        for func_decl in tools_list:
            if func_decl.name in available_tools:
                filtered_tools.append(func_decl)
        
        return filtered_tools
    
    def _format_stage_principles(self, stage_name: str, client_name: Optional[str] = None, client_phone_saved: bool = False) -> str:
        """
        Форматирует сценарий стадии в читаемую строку.
        
        Args:
            stage_name: Название стадии
            client_name: Имя клиента
            client_phone_saved: Сохранен ли телефон клиента
            
        Returns:
            Отформатированная строка со сценарием стадии
        """
        stage_data = self.dialogue_patterns.get(stage_name, {})
        scenario = stage_data.get('scenario', [])
        
        if not scenario:
            return "Будь вежливым, профессиональным и полезным. Всегда предоставляй точную информацию."
        
        # Добавляем информацию о клиенте, если она есть
        client_info = ""
        if client_name:
            client_info += f" Имя клиента: {client_name}."
        if client_phone_saved:
            client_info += " Телефон клиента сохранен в базе данных."
        
        # Форматируем сценарий в список
        formatted_scenario = []
        for step in scenario:
            formatted_scenario.append(step)
        
        result = "\n".join(formatted_scenario)
        if client_info:
            result += f"\n\nДополнительная информация:{client_info}"
        
        return result
    
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
        
        # Получаем список стадий из dialogue_patterns
        stage_list = ", ".join(self.dialogue_patterns.keys())
        
        # Собираем промпт по шаблону
        prompt = self.CLASSIFICATION_TEMPLATE.format(
            stage_list=stage_list,
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
        available_tools: Optional[List[str]] = None
    ) -> str:
        """
        Формирует промпт для Этапа 2: Мышление.
        
        Args:
            stage_name: Определенная стадия диалога
            history: История диалога
            user_message: Новое сообщение пользователя
            client_name: Имя клиента
            client_phone_saved: Сохранен ли телефон клиента
            available_tools: Список доступных инструментов для текущей стадии
            
        Returns:
            Промпт для этапа мышления
        """
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
        stage_scenario = self._format_stage_principles(stage_name, client_name, client_phone_saved)
        
        # Фильтруем read-only инструменты по доступным для текущей стадии
        filtered_read_only_tools = self._filter_tools_by_available(read_only_tools, available_tools)
        
        # Генерируем описание отфильтрованных read-only инструментов
        read_only_tools_summary = self._generate_tools_summary(filtered_read_only_tools)
        
        # Собираем промпт по шаблону
        prompt = self.THINKING_TEMPLATE.format(
            current_datetime=current_datetime,
            client_context=client_context,
            history=history_text,
            user_message=user_message,
            stage_name=stage_name,
            stage_scenario=stage_scenario,
            read_only_tools_summary=read_only_tools_summary
        )
        
        return prompt
    
    def build_synthesis_prompt(
        self,
        history: List[Dict],
        user_message: str,
        tool_results: str,
        client_name: Optional[str] = None,
        client_phone_saved: bool = False,
        available_tools: Optional[List[str]] = None
    ) -> str:
        """
        Формирует промпт для Этапа 3: Синтез.
        
        Args:
            history: История диалога
            user_message: Новое сообщение пользователя
            tool_results: Результаты выполнения инструментов с этапа мышления
            client_name: Имя клиента
            client_phone_saved: Сохранен ли телефон клиента
            available_tools: Список доступных инструментов для текущей стадии
            
        Returns:
            Промпт для этапа синтеза
        """
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
        
        # Фильтруем write инструменты по доступным для текущей стадии
        filtered_write_tools = self._filter_tools_by_available(write_tools, available_tools)
        
        # Генерируем описание отфильтрованных write инструментов
        write_tools_summary = self._generate_tools_summary(filtered_write_tools)
        
        # Собираем промпт по шаблону
        prompt = self.SYNTHESIS_TEMPLATE.format(
            current_datetime=current_datetime,
            client_context=client_context,
            history=history_text,
            user_message=user_message,
            tool_results=tool_results,
            write_tools_summary=write_tools_summary
        )
        
        return prompt