"""
Модифицированная версия main.py с заглушками для работы без БД.
Используется для тестирования webhook'ов когда БД не настроена.
"""
from fastapi import FastAPI, Request, BackgroundTasks
import logging
from app.core.config import settings
from app.api import telegram_stub
from app.services.dialogue_tracer_service import clear_debug_logs
from app.schemas.telegram import Update
from app.api.telegram_stub import process_telegram_update_stub

# Получаем логгер для этого модуля
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Beauty Salon AI Assistant (STUB Mode)",
    version="0.1.0-stub"
)

# Используем заглушку вместо оригинального роутера
app.include_router(telegram_stub.router, prefix="/telegram", tags=["Telegram-Stub"])


@app.on_event("startup")
async def startup_event():
    """Выполняется при запуске приложения."""
    logger.info("╔═══════════════════════════════════════════════════════════")
    logger.info("║ 🚀 Приложение запускается в режиме ЗАГЛУШКИ...")
    logger.info("╚═══════════════════════════════════════════════════════════")
    
    # Очищаем папку с логами при каждом запуске
    try:
        clear_debug_logs()
    except Exception as e:
        logger.warning(f"⚠️ Не удалось очистить папку debug_logs: {e}. В облачной среде это нормально.")


@app.get("/", tags=["Root"])
def root():
    """Корневой эндпоинт для проверки доступности сервиса."""
    return {
        "status": "OK", 
        "message": "Beauty Salon AI Assistant is running in STUB mode",
        "version": "0.1.0-stub",
        "mode": "stub",
        "database": "disabled"
    }


@app.post("/", tags=["Root"])
async def root_post(request: Request, background_tasks: BackgroundTasks):
    """
    POST обработчик для корневого пути с заглушками.
    Может обрабатывать как обычные запросы, так и Telegram webhook.
    Работает без базы данных.
    """
    try:
        # Пытаемся обработать как Telegram webhook
        update_data = await request.json()
        
        # Проверяем, что это Telegram update
        if "message" in update_data or "callback_query" in update_data:
            update = Update.parse_obj(update_data)
            background_tasks.add_task(process_telegram_update_stub, update)
            return {"status": "ok"}
        else:
            # Если это не Telegram update, возвращаем обычный ответ
            return {
                "status": "OK", 
                "message": "Beauty Salon AI Assistant is running in STUB mode",
                "version": "0.1.0-stub",
                "mode": "stub",
                "database": "disabled"
            }
    except Exception as e:
        logger.error(f"❌ Ошибка обработки POST запроса: {e}")
        # В случае ошибки возвращаем обычный ответ
        return {
            "status": "OK", 
            "message": "Beauty Salon AI Assistant is running in STUB mode",
            "version": "0.1.0-stub",
            "mode": "stub",
            "database": "disabled"
        }


@app.get("/healthcheck", tags=["Health Check"])
def health_check():
    """Простой эндпоинт для проверки работоспособности сервиса."""
    return {
        "status": "OK",
        "mode": "stub",
        "database": "disabled",
        "webhook": "enabled"
    }
