from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Модель загружает переменные из .env файла
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    # PostgreSQL Database
    DATABASE_URL: str

    # Telegram Bot
    TELEGRAM_BOT_TOKEN: str

    # Google AI
    GEMINI_API_KEY: str

# Создаем единственный экземпляр настроек, который будет использоваться во всем приложении
settings = Settings()

