"""
Сервис для построения промптов.
Отвечает за формирование всех типов промптов для диалоговой системы.
Реализует двухэтапную архитектуру: Классификация+Планирование -> Синтез.
"""

from typing import List, Dict, Optional
from datetime import datetime
from app.core.dialogue_pattern_loader import dialogue_patterns
from app.services.tool_definitions import salon_tools


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
        
        # Шаблон для Этапа 1: Классификация и Планирование
        self.classification_and_planning_template = """
# ЗАДАЧА
Тебе даны история диалога и новое сообщение клиента. Выполни ДВЕ задачи:
1. **Классифицируй** сообщение, присвоив ему ОДНУ из следующих стадий: {stage_list}.
2. **Спланируй** действия, выбрав один или несколько инструментов из списка ниже, которые необходимы для ответа.

# ПРАВИЛА
- Если для ответа на запрос нужна информация (цена, время, услуги), ты ДОЛЖЕН выбрать инструменты.
- Если информация не нужна (на "привет"), верни пустой список инструментов.

# ИНСТРУМЕНТЫ
{tools_summary}

# ИСТОРИЯ
{history}

# НОВОЕ СООБЩЕНИЕ
{user_message}

# ФОРМАТ ОТВЕТА
Ответь ТОЛЬКО в формате JSON, содержащем два ключа: 'stage' и 'tool_calls'.
Пример: {{"stage": "availability_check", "tool_calls": [{{"tool_name": "get_available_slots", "parameters": {{"date": "завтра"}}}}]}}

ВАЖНО: Твой ответ должен быть ТОЛЬКО валидным JSON без дополнительного текста!
"""

        # Шаблон для Этапа 2: Синтез финального ответа
        self.synthesis_template = """
# РОЛЬ И СТИЛЬ
Ты — Кэт, дружелюбный и профессиональный AI-администратор салона красоты.

# СТИЛЬ ОБЩЕНИЯ
- Всегда общайся на "вы".
- Отвечай кратко и по-человечески, как в мессенджере.
- Используй эмодзи сдержанно: при приветствии и после успешной записи.
- Если для ответа не нужна внешняя информация (например, на "спасибо"), просто вежливо ответь.

# РЕКОМЕНДАЦИИ ДЛЯ ТЕКУЩЕЙ СИТУАЦИИ (СТАДИЯ: {stage_name})
## Принципы:
{stage_principles}
## Примеры:
{stage_examples}

# ПОЛУЧЕННЫЕ ДАННЫЕ ОТ ИНСТРУМЕНТОВ
{tool_results}

# ТВОЯ ЗАДАЧА
Основываясь на своей роли, рекомендациях и полученных данных, сформулируй финальный, вежливый и краткий ответ для клиента.
"""
    
    def _generate_tools_summary(self) -> str:
        """
        Генерирует краткое описание всех доступных инструментов.
        
        Returns:
            Строка с кратким описанием инструментов
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
    
    def _format_examples(self, examples: List[Dict]) -> str:
        """
        Форматирует примеры стадии в читаемую строку.
        
        Args:
            examples: Список примеров из dialogue_patterns.json
            
        Returns:
            Отформатированная строка с примерами
        """
        if not examples:
            return "Примеры не предоставлены."
        
        formatted_examples = []
        for i, example in enumerate(examples, 1):
            user_msg = example.get('user', '')
            assistant_msg = example.get('assistant', '')
            formatted_examples.append(f"{i}. Пользователь: \"{user_msg}\"\n   Ответ: \"{assistant_msg}\"")
        
        return "\n\n".join(formatted_examples)
    
    def build_classification_and_planning_prompt(
        self, 
        history: List[Dict], 
        user_message: str
    ) -> str:
        """
        Формирует промпт для Этапа 1: Классификация и Планирование.
        
        Args:
            history: История диалога
            user_message: Новое сообщение пользователя
            
        Returns:
            Промпт для классификации и планирования
        """
        # Получаем список доступных стадий
        stages_list = ", ".join(list(self.dialogue_patterns.keys()))
        
        # Генерируем краткое описание инструментов
        tools_summary = self._generate_tools_summary()
        
        # Форматируем историю для промпта
        history_text = ""
        for msg in history:
            role = "Пользователь" if msg["role"] == "user" else "Ассистент"
            content = msg["parts"][0]["text"]
            history_text += f"{role}: {content}\n"
        
        # Собираем промпт по шаблону
        prompt = self.classification_and_planning_template.format(
            stage_list=stages_list,
            tools_summary=tools_summary,
            history=history_text.strip(),
            user_message=user_message
        )
        
        return prompt
    
    def build_synthesis_prompt(
        self, 
        stage: str, 
        tool_results: str,
        client_name: Optional[str] = None,
        client_phone_saved: bool = False
    ) -> str:
        """
        Формирует промпт для Этапа 2: Синтез финального ответа.
        
        Args:
            stage: ID стадии диалога
            tool_results: Результаты выполнения инструментов
            client_name: Имя клиента
            client_phone_saved: Сохранен ли телефон клиента
            
        Returns:
            Промпт для синтеза ответа
        """
        # Получаем данные стадии из dialogue_patterns.json
        stage_data = self.dialogue_patterns.get(stage, {})
        stage_name = stage_data.get('description', stage)
        stage_principles = self._format_principles(stage_data.get('principles', []), client_name, client_phone_saved)
        stage_examples = self._format_examples(stage_data.get('examples', []))
        
        # Собираем промпт по шаблону
        prompt = self.synthesis_template.format(
            stage_name=stage_name,
            stage_principles=stage_principles,
            stage_examples=stage_examples,
            tool_results=tool_results
        )
        
        return prompt
    
