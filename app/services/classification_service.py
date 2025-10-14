"""
Сервис классификации стадий диалога.
Отвечает за определение текущей стадии диалога на основе истории и сообщения пользователя.
"""

from typing import List, Dict, Optional, Tuple
import re
from app.core.dialogue_pattern_loader import dialogue_patterns
from app.services.llm_service import LLMService
from app.services.prompt_builder_service import PromptBuilderService
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
        self.prompt_builder = PromptBuilderService()
    
    async def get_dialogue_stage(self, history: List[Dict], user_message: str, user_id: int = None) -> Tuple[Optional[str], Dict[str, Optional[str]]]:
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
            # Быстрое извлечение ПДн регулярками (имя и телефон)
            extracted: Dict[str, Optional[str]] = {"name": None, "phone": None}
            # Телефон: российский формат, допускаем +7, 8, пробелы, дефисы, скобки
            phone_match = re.search(r"(?:\+7|8)?[\s-]*\(?\d{3}\)?[\s-]*\d{3}[\s-]*\d{2}[\s-]*\d{2}", user_message)
            if phone_match:
                phone = re.sub(r"[^\d+]", "", phone_match.group(0))
                if phone.startswith("8"):
                    phone = "+7" + phone[1:]
                elif not phone.startswith("+7") and len(phone) == 10:
                    phone = "+7" + phone
                extracted["phone"] = phone

            # Имя: более точная эвристика — сначала явные конструкции
            name_match = re.search(r"(?i)(?:меня\s+зовут|зовут\s+меня|я\s+—\s+|я\s+это\s+|это\s+)([A-ZА-ЯЁ][a-zа-яё]{1,20})", user_message)
            if name_match:
                extracted["name"] = name_match.group(1).capitalize()
            else:
                # Доп. эвристика: если сообщение содержит телефон и на отдельной строке есть слово с заглавной буквы — считаем это именем
                stopwords = {"Да", "Ок", "Окей", "Привет", "Здравствуйте", "Спасибо", "На", "Нет", "Добрый", "Доброе", "Вечер", "Утро", "День"}
                lines = [ln.strip() for ln in user_message.splitlines() if ln.strip()]
                candidate_name = None
                if lines:
                    # Если телефон найден, ищем имя в другой строке без цифр
                    if phone_match:
                        for ln in lines:
                            if any(ch.isdigit() for ch in ln):
                                continue
                            m = re.fullmatch(r"([A-ZА-ЯЁ][a-zа-яё]{2,20})", ln)
                            if m and m.group(1) not in stopwords:
                                candidate_name = m.group(1)
                                break
                    # Если телефон не найден, но всё сообщение — одно слово с заглавной, принимаем как имя (если не стоп-слово)
                    if not candidate_name and len(lines) == 1:
                        ln = lines[0]
                        if not any(ch.isdigit() for ch in ln):
                            m = re.fullmatch(r"([A-ZА-ЯЁ][a-zа-яё]{2,20})", ln)
                            if m and m.group(1) not in stopwords:
                                candidate_name = m.group(1)
                if candidate_name:
                    extracted["name"] = candidate_name.capitalize()
            # Получаем список доступных стадий
            stages = list(dialogue_patterns.keys())
            stages_list = ", ".join(stages)
            
            # Формируем промпт для классификации через PromptBuilderService
            classification_prompt = self.prompt_builder.build_classification_prompt(
                stages_list=stages_list,
                history=history,
                user_message=user_message
            )
            
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
            
            # Очищаем ответ от лишних пробелов, точек и других знаков препинания
            stage_id = response.strip().lower().rstrip('.,!?;:')
            
            # Отладочная информация
            print(f"[DEBUG] Классификация: получен ответ '{response}' -> очищенный '{stage_id}'")
            print(f"[DEBUG] Доступные стадии: {list(dialogue_patterns.keys())}")
            
            # Проверяем, что полученная стадия существует в паттернах
            if stage_id in dialogue_patterns:
                print(f"[Stage] {stage_id}")
                return stage_id, extracted
            
            # Если стадия не найдена или ответ пустой/некорректный - возвращаем None
            print("[Stage] unknown -> fallback")
            return None, extracted
            
        except Exception as e:
            # В случае ошибки возвращаем None для активации fallback
            print(f"Ошибка классификации стадии диалога: {e}")
            return None, {"name": None, "phone": None}
