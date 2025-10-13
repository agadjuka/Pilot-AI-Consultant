import asyncio
from typing import List, Dict
from vertexai.generative_models import GenerativeModel, Content, Part
import vertexai
from app.core.config import settings


class GeminiService:
    """Сервис для взаимодействия с моделью Gemini через Vertex AI."""
    
    def __init__(self):
        """
        Инициализирует клиент Vertex AI и модель Gemini.
        Использует учетные данные из переменной окружения GOOGLE_APPLICATION_CREDENTIALS.
        """
        # Инициализируем Vertex AI
        vertexai.init(
            project=settings.GCP_PROJECT_ID,
            location=settings.GCP_REGION
        )
        
        # Получаем модель Gemini
        self.model = GenerativeModel("gemini-1.5-flash-001")
        
        # Системная инструкция для персоны "Ева"
        self.system_instruction = """Ты — Ева, дружелюбный и профессиональный AI-ассистент салона красоты.
Твоя задача — помогать клиентам с записью на услуги, отвечать на вопросы о мастерах и услугах.
Общайся вежливо, по-дружески, но профессионально. Используй эмодзи там, где это уместно.
Если клиент хочет записаться, уточни желаемую услугу, мастера (если есть предпочтения) и удобное время."""

    async def generate_response(
        self,
        user_message: str,
        dialog_history: List[Dict[str, str]] = None
    ) -> str:
        """
        Генерирует ответ модели на основе сообщения пользователя и истории диалога.
        
        Args:
            user_message: Новое сообщение пользователя
            dialog_history: История диалога в формате [{"role": "user/model", "text": "..."}, ...]
            
        Returns:
            Текстовый ответ модели
        """
        # Формируем историю в формате, понятном Gemini
        contents = []
        
        # Добавляем системную инструкцию как первое сообщение от модели
        contents.append(
            Content(
                role="model",
                parts=[Part.from_text(self.system_instruction)]
            )
        )
        
        # Добавляем историю диалога, если она есть
        if dialog_history:
            for message in dialog_history:
                role = "user" if message["role"] == "user" else "model"
                contents.append(
                    Content(
                        role=role,
                        parts=[Part.from_text(message["text"])]
                    )
                )
        
        # Добавляем новое сообщение пользователя
        contents.append(
            Content(
                role="user",
                parts=[Part.from_text(user_message)]
            )
        )
        
        # Используем asyncio для выполнения синхронного вызова в асинхронном контексте
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            self._generate_content_sync,
            contents
        )
        
        return response

    def _generate_content_sync(self, contents: List[Content]) -> str:
        """
        Синхронная обертка для вызова API Gemini.
        
        Args:
            contents: Список Content объектов с историей диалога
            
        Returns:
            Текстовый ответ модели
        """
        # Создаем чат с историей
        chat = self.model.start_chat(history=contents[:-1])
        
        # Отправляем последнее сообщение
        response = chat.send_message(contents[-1].parts[0].text)
        
        return response.text


# Создаем единственный экземпляр сервиса
gemini_service = GeminiService()




