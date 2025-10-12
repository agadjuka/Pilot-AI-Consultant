from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
from app.core.config import settings

# Создаем движок SQLAlchemy на основе DATABASE_URL из настроек
engine = create_engine(settings.DATABASE_URL)

# Создаем фабрику сессий, которая будет создавать новые сессии для каждого запроса
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Создаем базовый класс для наших ORM моделей
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    Dependency для получения сессии базы данных.
    Используется в FastAPI endpoints для автоматического управления сессиями.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

