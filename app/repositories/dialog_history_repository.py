from typing import List
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.models.dialog_history import DialogHistory
from app.repositories.base import BaseRepository


class DialogHistoryRepository(BaseRepository[DialogHistory]):
    """Репозиторий для работы с историей диалогов."""

    def __init__(self, session: Session):
        super().__init__(DialogHistory, session)

    def get_recent_messages(self, user_id: int, limit: int = 20) -> List[DialogHistory]:
        """
        Получает последние N сообщений для указанного пользователя,
        отсортированных по времени (от старых к новым).
        
        Args:
            user_id: ID пользователя Telegram
            limit: Максимальное количество сообщений для получения
            
        Returns:
            Список объектов DialogHistory
        """
        messages = (
            self.db.query(self.model)
            .filter(self.model.user_id == user_id)
            .order_by(desc(self.model.timestamp))
            .limit(limit)
            .all()
        )
        # Возвращаем в хронологическом порядке (от старых к новым)
        return list(reversed(messages))

    def add_message(self, user_id: int, role: str, message_text: str) -> DialogHistory:
        """
        Добавляет новое сообщение в историю диалога.
        
        Args:
            user_id: ID пользователя Telegram
            role: Роль отправителя ('user' или 'model')
            message_text: Текст сообщения
            
        Returns:
            Созданный объект DialogHistory
        """
        message = DialogHistory(
            user_id=user_id,
            role=role,
            message_text=message_text
        )
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message

