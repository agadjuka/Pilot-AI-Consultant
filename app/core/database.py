from sqlalchemy import create_engine, Engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator, Optional
import logging

# Получаем логгер для этого модуля
logger = logging.getLogger(__name__)

# Создаем базовый класс для наших ORM моделей
Base = declarative_base()

# Глобальные переменные для ленивой инициализации
_engine: Optional[Engine] = None
_SessionLocal: Optional[sessionmaker] = None


def get_engine():
    """Получить или создать engine"""
    global _engine
    if _engine is None:
        from app.core.config import settings
        _engine = create_engine(settings.DATABASE_URL)
    return _engine


def get_session_local():
    """Получить или создать фабрику сессий"""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
    return _SessionLocal


def get_db() -> Generator[Session, None, None]:
    """
    Dependency для получения сессии базы данных.
    Используется в FastAPI endpoints для автоматического управления сессиями.
    """
    SessionLocal = get_session_local()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_database():
    """
    Инициализирует базу данных, создавая все таблицы.
    Вызывается при запуске приложения.
    """
    try:
        logger.info("🗄️ DATABASE: Инициализация базы данных...")
        
        # Импортируем все модели для создания таблиц
        from app.models import service, master, client, dialog_history, appointment
        
        # Создаем все таблицы
        Base.metadata.create_all(bind=get_engine())
        logger.info("✅ DATABASE: База данных успешно инициализирована")
        
    except Exception as e:
        logger.error(f"❌ DATABASE: Ошибка инициализации базы данных: {e}")
        raise

