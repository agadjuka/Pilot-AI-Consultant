from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # Модель загружает переменные из .env файла
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    # PostgreSQL Database
    DATABASE_URL: str

    # Telegram Bot
    TELEGRAM_BOT_TOKEN: str

    # Google Cloud Platform
    GCP_PROJECT_ID: str
    GCP_REGION: str
    GOOGLE_APPLICATION_CREDENTIALS: str
    GOOGLE_CALENDAR_ID: str

    # ChromaDB
    CHROMA_HOST: Optional[str] = None

# Глобальная переменная для ленивой инициализации
_settings: Optional[Settings] = None

def get_settings() -> Settings:
    """Получить или создать экземпляр настроек"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings

# Создаем экземпляр для обратной совместимости
# Используется во всем приложении
settings = get_settings()

