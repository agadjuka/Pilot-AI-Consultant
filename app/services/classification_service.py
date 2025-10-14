"""
Сервис классификации стадий диалога.
Отвечает за определение текущей стадии диалога на основе истории и сообщения пользователя.
"""

from typing import List, Dict, Optional
from app.core.dialogue_pattern_loader import dialogue_patterns
from app.services.llm_service import LLMService
from app.utils.debug_logger import gemini_debug_logger


class ClassificationService:
    """
    Сервис для определения стадии диалога.
    Использует быструю классификацию через Gemini для определения текущей стадии.
    """
    
    def __init__(self, llm_service: LLMService):
        """
        Инициализация сервиса классификации.
        
        Args:
            llm_service: Сервис для работы с LLM API (Gemini или YandexGPT)
        """
        self.llm_service = llm_service
    
    async def get_dialogue_stage(self, history: List[Dict], user_message: str, user_id: int = None) -> Optional[str]:
        """
        Определяет стадию диалога на основе истории и нового сообщения пользователя.
        
        Args:
            history: История диалога в формате списка сообщений
            user_message: Новое сообщение пользователя
            user_id: ID пользователя для логирования
            
        Returns:
            Optional[str]: ID стадии диалога или None если классификация не удалась
            
        Raises:
            Exception: При ошибке классификации
        """
        try:
            # Получаем список доступных стадий
            stages = list(dialogue_patterns.keys())
            stages_list = ", ".join(stages)
            
            # Формируем короткий и дешевый промпт для классификации
            classification_prompt = f"""Проанализируй историю диалога и новое сообщение пользователя. Определи, к какой из следующих стадий относится ПОСЛЕДНЕЕ сообщение: {stages_list}.

ВАЖНО: Если клиент выражает явное недовольство, жалуется, угрожает или прямо просит позвать человека, присвой стадию 'conflict_escalation'. Это высший приоритет.

В ответе укажи ТОЛЬКО ID стадии.

История: {history}
Новое сообщение: {user_message}"""
            
            # Создаем историю для классификации
            classification_history = [
                {
                    "role": "user",
                    "parts": [{"text": classification_prompt}]
                }
            ]
            
            # Вызываем LLM для классификации
            response = await self.llm_service.generate_response(classification_history)
            
            # Логируем классификацию
            if user_id is not None:
                gemini_debug_logger.log_simple_dialog(
                    user_id=user_id,
                    user_message=f"Классификация стадии диалога. История: {len(history)} сообщений, Новое сообщение: {user_message}",
                    system_prompt=f"Определи стадию диалога из: {stages_list}",
                    dialog_history=[],
                    gemini_response=response
                )
            
            # Очищаем ответ от лишних пробелов и символов
            stage_id = response.strip().lower()
            
            # Отладочная информация
            print(f"[DEBUG] Классификация: получен ответ '{response}' -> очищенный '{stage_id}'")
            print(f"[DEBUG] Доступные стадии: {list(dialogue_patterns.keys())}")
            
            # Проверяем, что полученная стадия существует в паттернах
            if stage_id in dialogue_patterns:
                print(f"[Stage] {stage_id}")
                return stage_id
            
            # Если стадия не найдена или ответ пустой/некорректный - возвращаем None
            print("[Stage] unknown -> fallback")
            return None
            
        except Exception as e:
            # В случае ошибки возвращаем None для активации fallback
            print(f"Ошибка классификации стадии диалога: {e}")
            return None
