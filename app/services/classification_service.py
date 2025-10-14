"""
Сервис классификации стадий диалога.
Отвечает за определение текущей стадии диалога на основе истории и сообщения пользователя.
"""

from typing import List, Dict, Optional
from app.core.dialogue_pattern_loader import dialogue_patterns
from app.services.gemini_service import GeminiService


class ClassificationService:
    """
    Сервис для определения стадии диалога.
    Использует быструю классификацию через Gemini для определения текущей стадии.
    """
    
    def __init__(self, gemini_service: GeminiService):
        """
        Инициализация сервиса классификации.
        
        Args:
            gemini_service: Сервис для работы с Gemini API
        """
        self.gemini_service = gemini_service
    
    async def get_dialogue_stage(self, history: List[Dict], user_message: str) -> Optional[str]:
        """
        Определяет стадию диалога на основе истории и нового сообщения пользователя.
        
        Args:
            history: История диалога в формате списка сообщений
            user_message: Новое сообщение пользователя
            
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
            classification_prompt = f"""Проанализируй историю диалога и новое сообщение пользователя. Определи, к какой из следующих стадий относится ПОСЛЕДНЕЕ сообщение пользователя: {stages_list}.
В ответе укажи ТОЛЬКО ID стадии. Не пиши ничего лишнего.

История: {history}
Новое сообщение: {user_message}"""
            
            # Создаем историю для классификации (только системное сообщение)
            classification_history = [
                {
                    "role": "user",
                    "parts": [{"text": classification_prompt}]
                }
            ]
            
            # Вызываем Gemini для классификации
            response = await self.gemini_service.generate_response(classification_history)
            
            # Очищаем ответ от лишних пробелов и символов
            stage_id = response.strip().lower()
            
            # Проверяем, что полученная стадия существует в паттернах
            if stage_id in dialogue_patterns:
                return stage_id
            
            # Если стадия не найдена или ответ пустой/некорректный - возвращаем None
            print(f"Классификация не удалась. Получен некорректный ответ: '{response}'")
            return None
            
        except Exception as e:
            # В случае ошибки возвращаем None для активации fallback
            print(f"Ошибка классификации стадии диалога: {e}")
            return None
