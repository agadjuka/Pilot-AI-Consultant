"""
Сервис для построения промптов.
Отвечает за формирование всех типов промптов для диалоговой системы.
Реализует двухэтапную архитектуру: Классификация -> Мышление и Речь.
"""

from typing import List, Dict, Optional
from datetime import datetime
from app.core.dialogue_pattern_loader import dialogue_patterns
from app.services.tool_definitions import read_only_tools, write_tools


class PromptBuilderService:
    """
    Сервис для построения промптов различных типов.
    Централизует всю логику формирования текстовых инструкций для LLM.
    Реализует двухэтапную архитектуру обработки диалогов.
    """
    
    def __init__(self):
        """
        Инициализирует сервис построения промптов.
        Загружает паттерны диалогов из конфигурации.
        """
        self.dialogue_patterns = dialogue_patterns
        
        # Шаблон для Этапа 1: Классификация (остается без изменений)
        self.CLASSIFICATION_TEMPLATE = """
Проанализируй историю диалога и новое сообщение. Определи стадию последнего сообщения из списка: {stage_list}.
ВАЖНО: Если клиент жалуется или просит позвать человека, присвой стадию 'conflict_escalation'.

В ответе укажи ТОЛЬКО ID стадии, без дополнительного текста.

## ИСТОРИЯ
{history}

## НОВОЕ СООБЩЕНИЕ
{user_message}

Ответ:"""

        # Старый шаблон MAIN_TEMPLATE удален - теперь используется динамическая логика в build_main_prompt
    
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
    
    def _format_scenario(self, scenario: List[str], client_name: Optional[str] = None, client_phone_saved: bool = False) -> str:
        """
        Форматирует сценарий стадии в читаемую строку.
        
        Args:
            scenario: Список шагов сценария из dialogue_patterns.json
            client_name: Имя клиента
            client_phone_saved: Сохранен ли телефон клиента
            
        Returns:
            Отформатированная строка с сценарием
        """
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
    
    def build_main_prompt(
        self, 
        stage_name: str,
        history: List[Dict],
        user_message: str,
        tool_results: str = "",
        client_name: Optional[str] = None,
        client_phone_saved: bool = False,
        use_all_tools: bool = True,
        iteration: int = 1
    ) -> str:
        """
        Формирует динамический промпт для Этапа 2: Мышление и Речь.
        Разделяет логику на первую итерацию (сбор данных) и последующие (синтез).
        
        Args:
            stage_name: Определенная стадия диалога
            history: История диалога
            user_message: Новое сообщение пользователя
            tool_results: Результаты выполнения инструментов с предыдущих итераций
            client_name: Имя клиента
            client_phone_saved: Сохранен ли телефон клиента
            use_all_tools: Использовать все инструменты (True) или только read-only (False)
            iteration: Номер итерации цикла (1 = сбор данных, >1 = синтез)
            
        Returns:
            Промпт для основного этапа мышления
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
        
        # Генерируем текущую дату и время
        current_datetime = self._generate_current_datetime()
        
        # ДИНАМИЧЕСКАЯ ЛОГИКА: Разделяем промпты по итерациям
        if iteration == 1:
            # --- ШАБЛОН ДЛЯ ПЕРВОЙ ИТЕРАЦИИ (СБОР ДАННЫХ) ---
            read_only_tools_summary = self._generate_tools_summary(read_only_tools)
            
            prompt = f"""
# ЗАДАЧА: Спланируй сбор данных.
Проанализируй запрос клиента и историю. Выбери "разведывательные" инструменты для сбора ВСЕЙ информации, необходимой для полного ответа.

# ДОСТУПНЫЕ ИНСТРУМЕНТЫ (только для сбора информации):
{read_only_tools_summary}

# КОНТЕКСТ
- Текущая дата: {current_datetime}
- О клиенте: {client_context}
- История диалога: {history_text}
- Последний запрос клиента: {user_message}

# ФОРМАТ ОТВЕТА:
Верни ТОЛЬКО JSON с вызовами инструментов `{{"tool_calls": [...]}}`. Никакого текста.
"""
        else: # iteration > 1
            # --- ШАБЛОН ДЛЯ ВТОРЫХ И ПОСЛЕДУЮЩИХ ИТЕРАЦИЙ (СИНТЕЗ) ---
            write_tools_summary = self._generate_tools_summary(write_tools)
            
            prompt = f"""
# РОЛЬ И СТИЛЬ
Ты — Кэт, AI-администратор салона красоты "Элегант". Ты дружелюбная, профессиональная и всегда готова помочь клиентам с записью на услуги. Твой стиль общения: теплый, но деловой, с легким юмором когда уместно. Ты всегда помнишь детали предыдущих разговоров и используешь их для персонализации общения.

# КОНТЕКСТ
- Текущая дата: {current_datetime}
- О клиенте: {client_context}
- История диалога: {history_text}
- Последний запрос клиента: {user_message}
- Собранные на предыдущем шаге данные: {tool_results}

# РЕКОМЕНДАЦИИ ПО СЦЕНАРИЮ (для стадии: {stage_name})
{stage_principles}

# ВОЗМОЖНЫЕ ДЕЙСТВИЯ (только сейчас)
{write_tools_summary}

# ГЛАВНАЯ ЗАДАЧА
Проанализируй весь контекст и реши, что делать дальше. У тебя два варианта:

1. **Если** ты готов совершить действие (создать/отменить/перенести запись), верни **гибридный ответ**: JSON с вызовом "исполнительного" инструмента, а следом — текст для клиента.

2. **Если** никакие инструменты не нужны (например, на "привет" или "спасибо"), просто верни **текстовый ответ**.

# ФОРМАТ ВЫЗОВА ИНСТРУМЕНТОВ
Для вызова инструментов используй строгий JSON формат:
```json
{{"tool_calls": [{{"tool_name": "название_инструмента", "parameters": {{"param1": "value1", "param2": "value2"}}}}]}}
```

ВАЖНО: 
- Если нужны инструменты + ответ клиенту — верни JSON, а затем текст
- Если инструменты не нужны — верни только текст

# ФИНАЛЬНЫЙ ОТВЕТ:
"""
        
        return prompt
    
    def build_planning_prompt(
        self,
        stage_name: str,
        stage_scenario: List[str],
        available_tools: List[str],
        history: List[Dict],
        user_message: str,
        client_name: Optional[str] = None,
        client_phone_saved: bool = False
    ) -> str:
        """
        Формирует промпт для планирования действий на основе сценария стадии.
        
        Args:
            stage_name: Название текущей стадии
            stage_scenario: Сценарий действий для стадии
            available_tools: Список доступных инструментов для стадии
            history: История диалога
            user_message: Новое сообщение пользователя
            client_name: Имя клиента
            client_phone_saved: Сохранен ли телефон клиента
            
        Returns:
            Промпт для планирования
        """
        # Форматируем историю диалога
        history_text = self._format_dialog_history(history)
        
        # Форматируем сценарий
        scenario_text = self._format_scenario(stage_scenario, client_name, client_phone_saved)
        
        # Формируем контекст клиента
        client_context_parts = []
        if client_name:
            client_context_parts.append(f"Имя: {client_name}")
        if client_phone_saved:
            client_context_parts.append("Телефон: сохранен в базе")
        
        client_context = ", ".join(client_context_parts) if client_context_parts else "Данные клиента не известны"
        
        # Генерируем текущую дату и время
        current_datetime = self._generate_current_datetime()
        
        # Формируем список доступных инструментов
        available_tools_summary = ""
        if available_tools:
            # Получаем все инструменты из tool_definitions
            from app.services.tool_definitions import all_tools_dict
            
            for tool_name in available_tools:
                if tool_name in all_tools_dict:
                    tool_decl = all_tools_dict[tool_name]
                    # Извлекаем параметры
                    params = []
                    if hasattr(tool_decl, 'parameters') and tool_decl.parameters:
                        params_dict = tool_decl.parameters
                        if hasattr(params_dict, 'properties') and params_dict.properties:
                            params = list(params_dict.properties.keys())
                    
                    if params:
                        params_str = ", ".join(params)
                        short_desc = tool_decl.description.split('.')[0]
                        available_tools_summary += f"- {tool_name}({params_str}): {short_desc}.\n"
                    else:
                        short_desc = tool_decl.description.split('.')[0]
                        available_tools_summary += f"- {tool_name}(): {short_desc}.\n"
        else:
            available_tools_summary = "На этой стадии инструменты не требуются."
        
        # Новый шаблон планирования
        prompt = f"""
# ЗАДАЧА
Проанализируй запрос клиента и историю. Определи, какие действия нужно выполнить для достижения цели стадии.

# СЦЕНАРИЙ ДЛЯ ТЕКУЩЕЙ СТАДИИ ({stage_name}):
{scenario_text}

# ДОСТУПНЫЕ ИНСТРУМЕНТЫ ДЛЯ ЭТОЙ СТАДИИ:
{available_tools_summary}

# КОНТЕКСТ
- Текущая дата: {current_datetime}
- О клиенте: {client_context}
- История диалога: {history_text}
- Последний запрос клиента: {user_message}

# ФОРМАТ ОТВЕТА:
Верни ТОЛЬКО JSON с вызовами инструментов `{{"tool_calls": [...]}}`. Никакого текста.
"""
        
        return prompt
    
    def build_synthesis_prompt(
        self,
        stage_name: str,
        stage_scenario: List[str],
        available_tools: List[str],
        history: List[Dict],
        user_message: str,
        tool_results: str = "",
        client_name: Optional[str] = None,
        client_phone_saved: bool = False
    ) -> str:
        """
        Формирует промпт для синтеза ответа на основе результатов инструментов.
        
        Args:
            stage_name: Название текущей стадии
            stage_scenario: Сценарий действий для стадии
            available_tools: Список доступных инструментов для стадии
            history: История диалога
            user_message: Новое сообщение пользователя
            tool_results: Результаты выполнения инструментов
            client_name: Имя клиента
            client_phone_saved: Сохранен ли телефон клиента
            
        Returns:
            Промпт для синтеза ответа
        """
        # Форматируем историю диалога
        history_text = self._format_dialog_history(history)
        
        # Форматируем сценарий
        scenario_text = self._format_scenario(stage_scenario, client_name, client_phone_saved)
        
        # Формируем контекст клиента
        client_context_parts = []
        if client_name:
            client_context_parts.append(f"Имя: {client_name}")
        if client_phone_saved:
            client_context_parts.append("Телефон: сохранен в базе")
        
        client_context = ", ".join(client_context_parts) if client_context_parts else "Данные клиента не известны"
        
        # Генерируем текущую дату и время
        current_datetime = self._generate_current_datetime()
        
        # Формируем список доступных инструментов
        available_tools_summary = ""
        if available_tools:
            # Получаем все инструменты из tool_definitions
            from app.services.tool_definitions import all_tools_dict
            
            for tool_name in available_tools:
                if tool_name in all_tools_dict:
                    tool_decl = all_tools_dict[tool_name]
                    # Извлекаем параметры
                    params = []
                    if hasattr(tool_decl, 'parameters') and tool_decl.parameters:
                        params_dict = tool_decl.parameters
                        if hasattr(params_dict, 'properties') and params_dict.properties:
                            params = list(params_dict.properties.keys())
                    
                    if params:
                        params_str = ", ".join(params)
                        short_desc = tool_decl.description.split('.')[0]
                        available_tools_summary += f"- {tool_name}({params_str}): {short_desc}.\n"
                    else:
                        short_desc = tool_decl.description.split('.')[0]
                        available_tools_summary += f"- {tool_name}(): {short_desc}.\n"
        else:
            available_tools_summary = "На этой стадии инструменты не требуются."
        
        # Шаблон синтеза
        prompt = f"""
# РОЛЬ И СТИЛЬ
Ты — Кэт, AI-администратор салона красоты "Элегант". Ты дружелюбная, профессиональная и всегда готова помочь клиентам с записью на услуги. Твой стиль общения: теплый, но деловой, с легким юмором когда уместно. Ты всегда помнишь детали предыдущих разговоров и используешь их для персонализации общения.

# КОНТЕКСТ
- Текущая дата: {current_datetime}
- О клиенте: {client_context}
- История диалога: {history_text}
- Последний запрос клиента: {user_message}
- Собранные данные: {tool_results}

# СЦЕНАРИЙ ДЛЯ ТЕКУЩЕЙ СТАДИИ ({stage_name}):
{scenario_text}

# ДОСТУПНЫЕ ИНСТРУМЕНТЫ ДЛЯ ЭТОЙ СТАДИИ:
{available_tools_summary}

# ГЛАВНАЯ ЗАДАЧА
Проанализируй весь контекст и реши, что делать дальше. У тебя два варианта:

1. **Если** ты готов совершить действие (создать/отменить/перенести запись), верни **гибридный ответ**: JSON с вызовом "исполнительного" инструмента, а следом — текст для клиента.

2. **Если** никакие инструменты не нужны (например, на "привет" или "спасибо"), просто верни **текстовый ответ**.

# ФОРМАТ ВЫЗОВА ИНСТРУМЕНТОВ
Для вызова инструментов используй строгий JSON формат:
```json
{{"tool_calls": [{{"tool_name": "название_инструмента", "parameters": {{"param1": "value1", "param2": "value2"}}}}]}}
```

ВАЖНО: 
- Если нужны инструменты + ответ клиенту — верни JSON, а затем текст
- Если инструменты не нужны — верни только текст

# ФИНАЛЬНЫЙ ОТВЕТ:
"""
        
        return prompt