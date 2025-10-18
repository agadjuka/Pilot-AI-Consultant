from fastapi import FastAPI
import logging
from app.core.config import settings
from app.api import telegram
from app.services.dialogue_tracer_service import clear_debug_logs

# Получаем логгер для этого модуля
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Beauty Salon AI Assistant",
    version="0.1.0"
)

app.include_router(telegram.router, prefix="/telegram", tags=["Telegram"])


@app.on_event("startup")
async def startup_event():
    """Выполняется при запуске приложения."""
    logger.info("╔═══════════════════════════════════════════════════════════")
    logger.info("║ 🚀 Приложение запускается...")
    logger.info("╚═══════════════════════════════════════════════════════════")
    
    # Очищаем папку с логами при каждом запуске
    try:
        clear_debug_logs()
    except Exception as e:
        logger.warning(f"Не удалось очистить папку debug_logs: {e}. В облачной среде это нормально.")


@app.get("/", tags=["Root"])
def root():
    """Корневой эндпоинт для проверки доступности сервиса."""
    return {
        "status": "OK", 
        "message": "Beauty Salon AI Assistant is running",
        "version": "0.1.0"
    }


@app.post("/", tags=["Root"])
def root_post():
    """POST обработчик для корневого пути (для совместимости с Yandex Cloud)."""
    return {
        "status": "OK", 
        "message": "Beauty Salon AI Assistant is running",
        "version": "0.1.0"
    }


@app.get("/healthcheck", tags=["Health Check"])
def health_check():
    """Простой эндпоинт для проверки работоспособности сервиса."""
    return {"status": "OK"}

