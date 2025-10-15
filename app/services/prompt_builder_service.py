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
- Если для ответа не нужна внешняя информация (например, на "привет" или "спасибо"), просто вежливо ответь, поддерживая диалог.

# РАБОТА С ИНФОРМАЦИЕЙ
- Твоя главная задача — предоставлять точную информацию.
- **Никогда не выдумывай** цены, услуги, имена мастеров или свободное время.
- Если для ответа на вопрос клиента тебе нужна информация, которой у тебя нет, **ты ДОЛЖЕН использовать один или несколько инструментов**.

# ПРАВИЛА ИСПОЛЬЗОВАНИЯ ИНСТРУМЕНТОВ
- Если ты решил использовать инструмент(ы), твой ответ должен быть ТОЛЬКО JSON-массивом с вызовами. Никакого другого текста.
- Ты можешь вызывать несколько инструментов одновременно.
- Формат: `[{{"tool_name": "...", "parameters": {{"...": "..."}}}}]`
- Если после анализа запроса ты понимаешь, что никакой инструмент не нужен, просто ответь текстом в соответствии со своим стилем общения.

# ДОСТУПНЫЕ ИНСТРУМЕНТЫ
{tools_summary}

# РЕКОМЕНДАЦИИ ДЛЯ ТЕКУЩЕЙ СИТУАЦИИ
{stage_principles}
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
    
    def _get_stage_principles(self, stage: str, client_name: Optional[str] = None, client_phone_saved: bool = False) -> str:
        """
        Получает принципы для текущей стадии диалога.
        
        Args:
            stage: ID стадии диалога
            client_name: Имя клиента
            client_phone_saved: Сохранен ли телефон клиента
            
        Returns:
            Строка с принципами для текущей стадии
        """
        # Базовые принципы для всех стадий
        base_principles = "Будь вежливым, профессиональным и полезным. Всегда предоставляй точную информацию."
        
        # Специфичные принципы для разных стадий
        stage_specific = {
            "greeting": "Поприветствуй клиента дружелюбно и предложи помощь. Используй эмодзи приветствия.",
            "service_inquiry": "Предоставь полную информацию об услугах. Если клиент спрашивает о конкретной услуге, покажи её детали.",
            "master_inquiry": "Покажи мастеров для выбранной услуги. Если услуга не выбрана, сначала уточни предпочтения.",
            "time_inquiry": "Покажи доступное время для записи. Если времени нет, предложи альтернативные даты.",
            "appointment_creation": "Создай запись с указанными параметрами. Если данных недостаточно, уточни их.",
            "appointment_management": "Помоги с управлением записями - покажи, отмени или перенеси.",
            "conflict_escalation": "Сохраняй спокойствие, извинись и передай ситуацию менеджеру."
        }
        
        # Добавляем информацию о клиенте, если она есть
        client_info = ""
        if client_name:
            client_info += f" Имя клиента: {client_name}."
        if client_phone_saved:
            client_info += " Телефон клиента сохранен в базе данных."
        
        # Возвращаем принципы для текущей стадии
        stage_principle = stage_specific.get(stage, base_principles)
        return f"{stage_principle}{client_info}"
    
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
        Использует новый гибридный подход.
        
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
        
        # Получаем принципы для текущей стадии
        stage_principles = self._get_stage_principles(stage, client_name, client_phone_saved)
        
        # Собираем промпт по новому шаблону
        system_prompt = self.system_prompt_template.format(
            tools_summary=tools_summary,
            stage_principles=stage_principles
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
        
        # Получаем базовые принципы для fallback режима
        stage_principles = self._get_stage_principles("greeting", client_name, client_phone_saved)
        
        # Собираем промпт по новому шаблону
        system_prompt = self.system_prompt_template.format(
            tools_summary=tools_summary,
            stage_principles=stage_principles
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
    
