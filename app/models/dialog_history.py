from sqlalchemy import Column, Integer, BigInteger, String, Text, DateTime
from datetime import datetime
from app.core.database import Base


class DialogHistory(Base):
    """Модель для хранения истории диалогов пользователей с ботом."""
    
    __tablename__ = "dialog_history"

    # Для SQLite используем Integer для автоинкремента
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(BigInteger, nullable=False, index=True)
    role = Column(String(10), nullable=False)  # 'user' или 'model'
    message_text = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)




