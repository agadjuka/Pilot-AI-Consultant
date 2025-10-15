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
        self.tools_description = self._generate_tools_description()
    
    def _generate_tools_description(self) -> str:
        """
        Генерирует текстовое описание всех доступных инструментов.
        
        Returns:
            Строка с описанием инструментов
        """
        tools_text = "Доступные инструменты:\n"
        
        for func_decl in salon_tools.function_declarations:
            tools_text += f"- {func_decl.name}: {func_decl.description}\n"
        
        return tools_text
    
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
        Использует новый агентский подход с универсальным системным промптом.
        
        Args:
            stage: ID стадии диалога
            dialog_history: История диалога
            dialog_context: Дополнительный контекст диалога
            client_name: Имя клиента (если известно)
            client_phone_saved: Сохранен ли телефон клиента
            
        Returns:
            Сформированный системный промпт
        """
        # Получаем принципы для текущей стадии
        stage_patterns = self.dialogue_patterns.get(stage, {})
        stage_principles = stage_patterns.get("principles", [])
        
        # Формируем принципы для текущей ситуации
        principles_text = ""
        if stage_principles:
            principles_text = "\n".join([f"- {principle}" for principle in stage_principles])
        
        # Формируем контекст диалога
        dialog_context_text = ""
        if not dialog_history:
            dialog_context_text = "Это первое сообщение клиента. Обязательно поздоровайся в ответ."
        if dialog_context:
            dialog_context_text = f"{dialog_context_text} {dialog_context}".strip()
        
        # Формируем контекст о клиенте
        client_context = self._build_client_context(client_name, client_phone_saved)
        
        # Собираем финальный промпт по новому шаблону
        system_prompt = f"""# РОЛЬ И ЦЕЛЬ
Ты — Кэт, AI-администратор салона красоты. Твоя задача — максимально эффективно помочь клиенту, используя доступные тебе инструменты.

# ОСНОВНЫЕ ПРИНЦИПЫ
- Будь краткой и вежливой.
- Никогда не выдумывай информацию. Если данных нет — используй инструмент.
- Ты можешь вызывать НЕСКОЛЬКО инструментов ОДНОВРЕМЕННО, если запрос клиента сложный.

# ТВОИ ИНСТРУМЕНТЫ (КНОПКИ)
{self.tools_description}

# КАК РАБОТАТЬ С ИНСТРУМЕНТАМИ
- Если клиент спрашивает об услугах — используй get_all_services
- Если клиент спрашивает о мастерах для услуги — используй get_masters_for_service
- Если клиент спрашивает о свободном времени — используй get_available_slots
- Если клиент хочет записаться — используй create_appointment
- Если клиент спрашивает о своих записях — используй get_my_appointments
- Если клиент хочет отменить запись — используй cancel_appointment_by_id
- Если клиент хочет перенести запись — используй reschedule_appointment_by_id
- Если ситуация конфликтная — используй call_manager

# РЕКОМЕНДАЦИИ ДЛЯ ТЕКУЩЕЙ СИТУАЦИИ
{principles_text}

# КОНТЕКСТ ДИАЛОГА
{dialog_context_text}"""
        
        if client_context:
            system_prompt += f"\n\n{client_context}"
        
        return system_prompt
    
    def build_fallback_prompt(
        self, 
        dialog_context: str = "",
        client_name: Optional[str] = None,
        client_phone_saved: bool = False
    ) -> str:
        """
        Формирует универсальный промпт для fallback режима.
        
        Args:
            dialog_context: Дополнительный контекст диалога
            client_name: Имя клиента (если известно)
            client_phone_saved: Сохранен ли телефон клиента
            
        Returns:
            Универсальный системный промпт
        """
        # Формируем контекст диалога
        dialog_context_text = ""
        if dialog_context:
            dialog_context_text = dialog_context
        
        # Формируем контекст о клиенте
        client_context = self._build_client_context(client_name, client_phone_saved)
        
        # Собираем финальный промпт по новому шаблону
        system_prompt = f"""# РОЛЬ И ЦЕЛЬ
Ты — Кэт, AI-администратор салона красоты. Твоя задача — максимально эффективно помочь клиенту, используя доступные тебе инструменты.

# ОСНОВНЫЕ ПРИНЦИПЫ
- Будь краткой и вежливой.
- Никогда не выдумывай информацию. Если данных нет — используй инструмент.
- Ты можешь вызывать НЕСКОЛЬКО инструментов ОДНОВРЕМЕННО, если запрос клиента сложный.

# ТВОИ ИНСТРУМЕНТЫ (КНОПКИ)
{self.tools_description}

# КАК РАБОТАТЬ С ИНСТРУМЕНТАМИ
- Если клиент спрашивает об услугах — используй get_all_services
- Если клиент спрашивает о мастерах для услуги — используй get_masters_for_service
- Если клиент спрашивает о свободном времени — используй get_available_slots
- Если клиент хочет записаться — используй create_appointment
- Если клиент спрашивает о своих записях — используй get_my_appointments
- Если клиент хочет отменить запись — используй cancel_appointment_by_id
- Если клиент хочет перенести запись — используй reschedule_appointment_by_id
- Если ситуация конфликтная — используй call_manager

# РЕКОМЕНДАЦИИ ДЛЯ ТЕКУЩЕЙ СИТУАЦИИ
- Если клиент задает вопрос не по теме салона красоты, вежливо верни диалог к услугам салона.
- Если ситуация становится конфликтной, используй инструмент 'call_manager'.

# КОНТЕКСТ ДИАЛОГА
{dialog_context_text}"""
        
        if client_context:
            system_prompt += f"\n\n{client_context}"
        
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
    
    def _build_client_context(self, client_name: Optional[str] = None, client_phone_saved: bool = False) -> str:
        """
        Формирует контекст о клиенте для промпта.
        
        Args:
            client_name: Имя клиента (если известно)
            client_phone_saved: Сохранен ли телефон клиента
            
        Returns:
            Строка с контекстом о клиенте
        """
        if client_name and client_phone_saved:
            return f"КОНТЕКСТ: Клиента зовут {client_name}, телефон сохранён. Обращайся к нему по имени, где это уместно."
        elif client_name:
            return f"КОНТЕКСТ: Клиента зовут {client_name}. Обращайся к нему по имени, где это уместно."
        elif client_phone_saved:
            return "КОНТЕКСТ: Телефон клиента сохранён."
        else:
            return "КОНТЕКСТ: Данные клиента не сохранены."
