try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Модель загружает переменные из .env файла
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore"
    }

    # YDB Configuration
    YDB_ENDPOINT: str = "grpcs://ydb.serverless.yandexcloud.net:2135"
    YDB_DATABASE: str = "/ru-central1/b1gogvdsgf3hje2flr3i/etnci59p991a6s9vd1g4"
    # В Serverless Container используется автоматическая аутентификация через IAM токен

    # Telegram Bot
    TELEGRAM_BOT_TOKEN: Optional[str] = None

    # ChromaDB
    CHROMA_HOST: Optional[str] = None

    # LLM Provider Configuration
    LLM_PROVIDER: str = "google"  # "google" или "yandex"

    # YandexGPT Configuration
    YANDEX_FOLDER_ID: Optional[str] = None
    YANDEX_API_KEY_SECRET: Optional[str] = None

    # Logging Configuration
    LOG_MODE: str = "local"  # "local" или "cloud"

    # S3 Configuration (для облачного режима логирования)
    S3_ACCESS_KEY_ID: Optional[str] = None
    S3_SECRET_ACCESS_KEY: Optional[str] = None
    S3_BUCKET_NAME: Optional[str] = None
    S3_ENDPOINT_URL: str = "https://storage.yandexcloud.net"

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

