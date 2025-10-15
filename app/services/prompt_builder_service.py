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
# ЗАДАЧА
Твоя задача — помочь клиенту салона красоты. Проанализируй его запрос и вызови один или несколько инструментов для получения информации или выполнения действия. После получения ответа от инструментов, сформулируй короткий, естественный ответ для клиента.

# ПРАВИЛА
1.  **ВСЕГДА ИСПОЛЬЗУЙ ИНСТРУМЕНТЫ.** Не отвечай на вопросы о ценах, времени, услугах или мастерах из головы. Твой ответ должен быть основан только на данных, полученных от инструментов.
2.  **МОЖНО ВЫЗЫВАТЬ НЕСКОЛЬКО ИНСТРУМЕНТОВ СРАЗУ.** Если запрос сложный, вызови все необходимые инструменты одновременно.
3.  **ФОРМАТ ВЫЗОВА:** Отвечай ТОЛЬКО JSON-массивом с вызовами инструментов. Никакого другого текста.
    Пример: [{{"tool_name": "get_all_services"}}, {{"tool_name": "get_available_slots", "parameters": {{"date": "завтра"}}}}]
    Если никакой инструмент не нужен, верни пустой массив [].

# ДОСТУПНЫЕ ИНСТРУМЕНТЫ
{tools_summary}

# ИСТОРИЯ ДИАЛОГА
{history}

# ЗАПРОС КЛИЕНТА
{user_message}
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
        Использует новый упрощенный агентский подход.
        
        Args:
            stage: ID стадии диалога (не используется в новом подходе)
            dialog_history: История диалога
            dialog_context: Дополнительный контекст диалога (не используется)
            client_name: Имя клиента (не используется)
            client_phone_saved: Сохранен ли телефон клиента (не используется)
            
        Returns:
            Сформированный системный промпт
        """
        # Получаем последнее сообщение пользователя
        user_message = ""
        if dialog_history:
            last_message = dialog_history[-1]
            if last_message.get("role") == "user":
                # Извлекаем текст из структуры Gemini
                if "parts" in last_message:
                    user_message = last_message["parts"][0].get("text", "")
                else:
                    user_message = last_message.get("content", "")
        
        # Формируем историю диалога в текстовом виде
        history_text = ""
        for msg in dialog_history[:-1]:  # Исключаем последнее сообщение (текущий запрос)
            role = msg.get("role", "")
            if role == "user":
                if "parts" in msg:
                    content = msg["parts"][0].get("text", "")
                else:
                    content = msg.get("content", "")
                history_text += f"Клиент: {content}\n"
            elif role == "assistant":
                if "parts" in msg:
                    content = msg["parts"][0].get("text", "")
                else:
                    content = msg.get("content", "")
                history_text += f"Ассистент: {content}\n"
        
        # Генерируем краткое описание инструментов
        tools_summary = self._generate_tools_summary()
        
        # Собираем промпт по новому шаблону
        system_prompt = self.system_prompt_template.format(
            tools_summary=tools_summary,
            history=history_text.strip() or "История диалога пуста",
            user_message=user_message or "Нет сообщения"
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
        Использует тот же упрощенный подход, что и основной промпт.
        
        Args:
            dialog_context: Дополнительный контекст диалога (не используется)
            client_name: Имя клиента (не используется)
            client_phone_saved: Сохранен ли телефон клиента (не используется)
            
        Returns:
            Универсальный системный промпт
        """
        # Генерируем краткое описание инструментов
        tools_summary = self._generate_tools_summary()
        
        # Собираем промпт по новому шаблону
        system_prompt = self.system_prompt_template.format(
            tools_summary=tools_summary,
            history="История диалога пуста",
            user_message="Нет сообщения"
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
    
