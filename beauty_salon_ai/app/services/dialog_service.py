from typing import List, Dict
from sqlalchemy.orm import Session
from app.repositories.dialog_history_repository import DialogHistoryRepository
from app.services.gemini_service import gemini_service


class DialogService:
    """
    Оркестратор диалоговой логики.
    Координирует работу между хранилищем истории диалогов и AI-моделью.
    """
    
    def __init__(self, db_session: Session):
        """
        Инициализирует сервис диалога.
        
        Args:
            db_session: Сессия базы данных SQLAlchemy
        """
        self.repository = DialogHistoryRepository(db_session)
        self.gemini_service = gemini_service

    async def process_user_message(self, user_id: int, text: str) -> str:
        """
        Обрабатывает сообщение пользователя:
        1. Получает историю диалога из БД
        2. Сохраняет новое сообщение пользователя
        3. Генерирует ответ через Gemini
        4. Сохраняет ответ бота в БД
        5. Возвращает сгенерированный текст
        
        Args:
            user_id: ID пользователя Telegram
            text: Текст сообщения пользователя
            
        Returns:
            Сгенерированный ответ бота
        """
        # 1. Получаем историю диалога (последние 20 сообщений)
        history_records = self.repository.get_recent_messages(user_id, limit=20)
        
        # Преобразуем историю в формат для Gemini
        dialog_history: List[Dict[str, str]] = [
            {
                "role": record.role,
                "text": record.message_text
            }
            for record in history_records
        ]
        
        # 2. Сохраняем новое сообщение пользователя в БД
        self.repository.add_message(
            user_id=user_id,
            role="user",
            message_text=text
        )
        
        # 3. Генерируем ответ через Gemini
        bot_response = await self.gemini_service.generate_response(
            user_message=text,
            dialog_history=dialog_history
        )
        
        # 4. Сохраняем ответ бота в БД
        self.repository.add_message(
            user_id=user_id,
            role="model",
            message_text=bot_response
        )
        
        # 5. Возвращаем сгенерированный текст
        return bot_response

