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
    """Получить или создать engine для YDB."""
    global _engine
    if _engine is None:
        from app.core.config import settings
        import ydb
        import os
        
        # Формируем строку подключения
        endpoint = settings.YDB_ENDPOINT
        database = settings.YDB_DATABASE
        # Убираем grpcs:// из endpoint для правильного парсинга
        endpoint_clean = endpoint.replace('grpcs://', '').replace('grpc://', '')
        connection_string = f"ydb://{endpoint_clean}/{database}"
        
        # Получаем учетные данные из Service Account ключа
        service_account_key_file = os.getenv("YC_SERVICE_ACCOUNT_KEY_FILE", "key.json")
        
        # Проверяем существование файла ключа
        # Сначала проверяем относительный путь, затем в корне проекта
        key_file_path = service_account_key_file
        if not os.path.exists(key_file_path):
            # Пробуем найти файл в корне проекта
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            key_file_path = os.path.join(project_root, service_account_key_file)
        
        credentials = ydb.iam.ServiceAccountCredentials.from_file(key_file_path)
        
        _engine = create_engine(
            connection_string,
            connect_args={"credentials": credentials}
        )
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

