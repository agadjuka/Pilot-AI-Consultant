"""
Сервис для построения промптов.
Отвечает за формирование всех типов промптов для диалоговой системы.
"""

from typing import List, Dict, Optional
from datetime import datetime
from app.core.dialogue_pattern_loader import dialogue_patterns
from app.services.tool_definitions import salon_tools


class PromptBuilderService:
    """
    Сервис для построения промптов различных типов.
    Централизует всю логику формирования текстовых инструкций для LLM.
    """
    
    def __init__(self):
        """
        Инициализирует сервис построения промптов.
        Загружает паттерны диалогов из конфигурации.
        """
        self.dialogue_patterns = dialogue_patterns
        self.system_prompt_template = """
# РОЛЬ
Ты — Кэт, дружелюбный и профессиональный AI-администратор салона красоты.

# СТИЛЬ ОБЩЕНИЯ
- Всегда общайся на "вы".
- Отвечай кратко и по-человечески, как в мессенджере.
- Используй эмодзи сдержанно: при приветствии и после успешной записи.
- Если для ответа не нужна внешняя информация (например, на "спасибо"), просто вежливо ответь.

# РАБОТА С ИНФОРМАЦИЕЙ И ИНСТРУМЕНТАМИ
- Твоя главная задача — предоставлять точную информацию. **Никогда не выдумывай** цены, время или услуги.
- Если для ответа нужна информация, **ты ДОЛЖЕН использовать один или несколько инструментов**.
- **Правила вызова:** Если ты решил использовать инструмент(ы), твой ответ должен быть ТОЛЬКО JSON-массивом с вызовами. В противном случае — отвечай обычным текстом.
- Формат вызова: `[{{"tool_name": "...", "parameters": {{"...": "..."}}}}]`

# ДОСТУПНЫЕ ИНСТРУМЕНТЫ
{tools_summary}

# РЕКОМЕНДАЦИИ И ПРИМЕРЫ ДЛЯ ТЕКУЩЕЙ СИТУАЦИИ (СТАДИЯ: {stage_name})
## Принципы:
{stage_principles}
## Примеры:
{stage_examples}

# КОНТЕКСТ ДИАЛОГА
{dialog_context}
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
    
    
    def build_classification_prompt(self, stages_list: str, history: List[Dict], user_message: str) -> str:
        """
        Формирует промпт для классификации стадии диалога.
        
        Args:
            stages_list: Список доступных стадий в виде строки
            history: История диалога
            user_message: Новое сообщение пользователя
            
        Returns:
            Промпт для классификации стадии
        """
        return f"""Проанализируй историю диалога и новое сообщение пользователя. Определи, к какой из следующих стадий относится ПОСЛЕДНЕЕ сообщение: {stages_list}.

ВАЖНО: Если клиент выражает явное недовольство, жалуется, угрожает или прямо просит позвать человека, присвой стадию 'conflict_escalation'. Это высший приоритет.

В ответе укажи ТОЛЬКО ID стадии.

История: {history}
Новое сообщение: {user_message}"""
    
    def build_generation_prompt(
        self, 
        stage: str, 
        dialog_history: List[Dict], 
        dialog_context: str = "",
        client_name: Optional[str] = None,
        client_phone_saved: bool = False
    ) -> str:
        """
        Формирует основной промпт для генерации ответа на основе стадии диалога.
        Использует новый гибридный подход с принципами и примерами из dialogue_patterns.json.
        
        Args:
            stage: ID стадии диалога
            dialog_history: История диалога
            dialog_context: Дополнительный контекст диалога
            client_name: Имя клиента
            client_phone_saved: Сохранен ли телефон клиента
            
        Returns:
            Сформированный системный промпт
        """
        # Генерируем краткое описание инструментов
        tools_summary = self._generate_tools_summary()
        
        # Получаем данные стадии из dialogue_patterns.json
        stage_data = self.dialogue_patterns.get(stage, {})
        stage_name = stage_data.get('description', stage)
        stage_principles = self._format_principles(stage_data.get('principles', []), client_name, client_phone_saved)
        stage_examples = self._format_examples(stage_data.get('examples', []))
        
        # Собираем промпт по новому шаблону
        system_prompt = self.system_prompt_template.format(
            tools_summary=tools_summary,
            stage_name=stage_name,
            stage_principles=stage_principles,
            stage_examples=stage_examples,
            dialog_context=dialog_context
        )
        
        return system_prompt
    
    def build_fallback_prompt(
        self, 
        dialog_context: str = "",
        client_name: Optional[str] = None,
        client_phone_saved: bool = False
    ) -> str:
        """
        Формирует универсальный промпт для fallback режима.
        Использует новый гибридный подход.
        
        Args:
            dialog_context: Дополнительный контекст диалога
            client_name: Имя клиента
            client_phone_saved: Сохранен ли телефон клиента
            
        Returns:
            Универсальный системный промпт
        """
        # Генерируем краткое описание инструментов
        tools_summary = self._generate_tools_summary()
        
        # Получаем данные стадии fallback из dialogue_patterns.json
        stage_data = self.dialogue_patterns.get('fallback', {})
        stage_name = stage_data.get('description', 'fallback')
        stage_principles = self._format_principles(stage_data.get('principles', []), client_name, client_phone_saved)
        stage_examples = self._format_examples(stage_data.get('examples', []))
        
        # Собираем промпт по новому шаблону
        system_prompt = self.system_prompt_template.format(
            tools_summary=tools_summary,
            stage_name=stage_name,
            stage_principles=stage_principles,
            stage_examples=stage_examples,
            dialog_context=dialog_context
        )
        
        return system_prompt
    
    def build_full_history_with_system_prompt(self, dialog_history: List[Dict], system_prompt: str) -> List[Dict]:
        """
        Формирует полную историю диалога с системной инструкцией.
        
        Args:
            dialog_history: История диалога
            system_prompt: Системный промпт
            
        Returns:
            Полная история с системной инструкцией
        """
        # Получаем текущую дату и время
        current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Добавляем информацию о текущей дате и времени к системному промпту
        enhanced_system_prompt = f"{system_prompt}\n\nТекущая дата и время: {current_datetime}"
        
        # Добавляем системную инструкцию в начало истории
        full_history = [
            {
                "role": "user",
                "parts": [{"text": enhanced_system_prompt}]
            }
        ]
        
        # Добавляем историю диалога
        full_history.extend(dialog_history)
        
        return full_history
    
