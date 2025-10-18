from sqlalchemy import Column, Integer, BigInteger, String, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.core.database import Base


class Appointment(Base):
    """Модель для хранения информации о записях клиентов"""
    
    __tablename__ = "appointments"
    
    id = Column(Integer, primary_key=True, index=True)
    user_telegram_id = Column(BigInteger, nullable=False, index=True)
    master_id = Column(Integer, ForeignKey("masters.id"), nullable=False)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    
    # Relationships
    master = relationship("Master", back_populates="appointments")
    service = relationship("Service", back_populates="appointments")
    
    # Индекс для быстрого поиска по пользователю и времени
    __table_args__ = (
        Index('idx_user_time', 'user_telegram_id', 'start_time'),
    )
