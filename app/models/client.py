from sqlalchemy import Column, Integer, String, UniqueConstraint
from app.core.database import Base


class Client(Base):
    __tablename__ = "clients"
    __table_args__ = (
        UniqueConstraint("telegram_id", name="uq_clients_telegram_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, nullable=False, unique=True, index=True)
    first_name = Column(String(255), nullable=True)
    phone_number = Column(String(32), nullable=True)


