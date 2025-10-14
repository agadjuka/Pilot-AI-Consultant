"""
Сервис для построения промптов.
Отвечает за формирование всех типов промптов для диалоговой системы.
"""

from typing import List, Dict, Optional
from datetime import datetime
from app.core.dialogue_pattern_loader import dialogue_patterns


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
        
        Args:
            stage: ID стадии диалога
            dialog_history: История диалога
            dialog_context: Дополнительный контекст диалога
            client_name: Имя клиента (если известно)
            client_phone_saved: Сохранен ли телефон клиента
            
        Returns:
            Сформированный системный промпт
        """
        # Получаем паттерны для стадии
        stage_patterns = self.dialogue_patterns.get(stage, {})
        
        # Проверяем, есть ли у стадии принципы и примеры (обычные стадии)
        if "principles" in stage_patterns and "examples" in stage_patterns:
            principles = stage_patterns.get("principles", [])
            examples = stage_patterns.get("examples", [])
            proactive_params = stage_patterns.get("proactive_params", {})
            
            return self._build_dynamic_system_prompt(
                principles=principles,
                examples=examples,
                dialog_history=dialog_history,
                proactive_params=proactive_params,
                extra_context=dialog_context,
                client_name=client_name,
                client_phone_saved=client_phone_saved
            )
        else:
            # Специальная стадия - используем fallback
            return self._build_fallback_system_prompt(
                extra_context=dialog_context,
                client_name=client_name,
                client_phone_saved=client_phone_saved
            )
    
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
        return self._build_fallback_system_prompt(
            extra_context=dialog_context,
            client_name=client_name,
            client_phone_saved=client_phone_saved
        )
    
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
    
    def _build_dynamic_system_prompt(
        self, 
        principles: List[str], 
        examples: List[str], 
        dialog_history: List[Dict], 
        proactive_params: Dict = None, 
        extra_context: str = "",
        client_name: Optional[str] = None,
        client_phone_saved: bool = False
    ) -> str:
        """
        Формирует динамический системный промпт на основе паттернов стадии диалога.
        
        Args:
            principles: Принципы для текущей стадии диалога
            examples: Примеры для текущей стадии диалога
            dialog_history: История диалога
            proactive_params: Параметры для самостоятельного определения ботом
            extra_context: Дополнительный контекст
            client_name: Имя клиента (если известно)
            client_phone_saved: Сохранен ли телефон клиента
            
        Returns:
            Сформированный системный промпт
        """
        # Базовая персона
        base_persona = """Ты — Кэт, вежливый и услужливый администратор салона красоты "Элегант". Твоя задача — помочь клиентам записаться на услуги, предоставить информацию о мастерах и услугах, ответить на вопросы о ценах и расписании.

Твой стиль общения:
- Дружелюбный и профессиональный
- Используй эмодзи ТОЛЬКО в двух случаях: при приветствии клиента и при подтверждении записи
- В остальных сообщениях общайся без эмодзи, но сохраняй дружелюбный тон
- Будь конкретным в ответах
- Всегда предлагай конкретные варианты записи
- Если информации недостаточно — задавай уточняющие вопросы"""

        # Определяем контекст диалога
        dialog_context = ""
        if not dialog_history:
            dialog_context = "Это первое сообщение клиента. Обязательно поздоровайся в ответ."
        if extra_context:
            dialog_context = f"{dialog_context} {extra_context}".strip()

        # Формируем контекст о клиенте
        client_context = self._build_client_context(client_name, client_phone_saved)

        # Всегда проговариваем правило работы с недостающими/имеющимися ПДн
        pdn_rule = (
            "\n\nПравило ПДн: Если в контексте указано, что имя и/или телефон клиента не сохранены — при оформлении записи аккуратно запроси недостающие данные. "
            "Если указано, что оба сохранены — не запрашивай их повторно и оформляй запись сразу."
        )

        # Формируем принципы
        principles_text = ""
        if principles:
            principles_text = "\n\nПринципы для текущей стадии диалога:\n"
            for i, principle in enumerate(principles, 1):
                principles_text += f"{i}. {principle}\n"

        # Формируем примеры
        examples_text = ""
        if examples:
            examples_text = "\n\nПримеры ответов для текущей стадии:\n"
            for i, example in enumerate(examples, 1):
                examples_text += f"{i}. {example}\n"

        # Формируем секцию с proactive_params
        proactive_params_text = ""
        if proactive_params and isinstance(proactive_params, dict):
            proactive_params_text = "\n\n# ПРАВИЛА САМОСТОЯТЕЛЬНЫХ ДЕЙСТВИЙ (PROACTIVE ACTIONS)\n"
            proactive_params_text += "На текущей стадии диалога, при вызове инструментов, ты можешь самостоятельно определять следующие параметры, если они не указаны клиентом явно:\n"
            
            for tool_name, params in proactive_params.items():
                if isinstance(params, dict):
                    proactive_params_text += f"- Для инструмента '{tool_name}':\n"
                    for param_name, description in params.items():
                        proactive_params_text += f"  - {param_name}: {description}\n"

        # Собираем финальный промпт
        system_prompt = f"{base_persona}{principles_text}{examples_text}{proactive_params_text}{pdn_rule}"
        
        if client_context:
            system_prompt += f"\n\n{client_context}"
        
        if dialog_context:
            system_prompt += f"\n\nКонтекст диалога: {dialog_context}"

        return system_prompt
    
    def _build_fallback_system_prompt(
        self, 
        extra_context: str = "",
        client_name: Optional[str] = None,
        client_phone_saved: bool = False
    ) -> str:
        """
        Формирует универсальный системный промпт для fallback режима.
        Используется когда классификация стадии диалога не удалась.
        
        Args:
            extra_context: Дополнительный контекст
            client_name: Имя клиента (если известно)
            client_phone_saved: Сохранен ли телефон клиента
        
        Returns:
            Универсальный системный промпт
        """
        base = """Ты — Кэт, вежливый и услужливый администратор салона красоты "Элегант". 

Твоя основная задача — помогать клиентам с записью на услуги салона красоты. 

Если клиент задает вопрос не по теме салона красоты (например, о науке, политике, личных темах), вежливо ответь, что ты не можешь помочь с этим, и верни диалог к услугам салона.

Всегда будь дружелюбной, используй эмодзи ТОЛЬКО при приветствии клиента и при подтверждении записи. В остальных сообщениях общайся без эмодзи, но сохраняй дружелюбный тон. Предлагай конкретные варианты записи на услуги салона.

Однако, если ситуация становится конфликтной, клиент жалуется или просит позвать человека, используй инструмент 'call_manager', чтобы передать диалог менеджеру."""
        
        # Формируем контекст о клиенте
        client_context = self._build_client_context(client_name, client_phone_saved)
        
        result = base
        if client_context:
            result += f"\n\n{client_context}"
        if extra_context:
            result += f"\n\n{extra_context}"
        
        return result
    
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
