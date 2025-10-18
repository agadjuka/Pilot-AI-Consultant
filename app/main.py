from fastapi import FastAPI, Request, BackgroundTasks
import logging
from app.core.config import settings
from app.api import telegram
from app.services.dialogue_tracer_service import clear_debug_logs
from app.schemas.telegram import Update
from app.api.telegram import process_telegram_update
from app.core.database import init_database

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
    
    logger.info("🔧 STARTUP: Инициализация приложения")
    logger.info(f"📊 STARTUP: Режим логирования: {settings.LOG_MODE}")
    logger.info(f"🤖 STARTUP: LLM провайдер: {settings.LLM_PROVIDER}")
    logger.info(f"📱 STARTUP: Telegram токен настроен: {'Да' if settings.TELEGRAM_BOT_TOKEN else 'Нет'}")
    logger.info(f"🗄️ STARTUP: База данных: {settings.DATABASE_URL}")
    
    # Инициализируем базу данных
    try:
        init_database()
        logger.info("✅ STARTUP: База данных инициализирована")
    except Exception as e:
        logger.error(f"❌ STARTUP: Ошибка инициализации базы данных: {e}")
        raise
    
    # Очищаем папку с логами при каждом запуске
    try:
        clear_debug_logs()
        logger.info("🧹 STARTUP: Папка debug_logs очищена")
    except Exception as e:
        logger.warning(f"⚠️ STARTUP: Не удалось очистить папку debug_logs: {e}. В облачной среде это нормально.")
    
    logger.info("✅ STARTUP: Приложение успешно запущено и готово к работе")


@app.get("/", tags=["Root"])
def root():
    """Корневой эндпоинт для проверки доступности сервиса."""
    return {
        "status": "OK", 
        "message": "Beauty Salon AI Assistant is running",
        "version": "0.1.0",
        "database": "enabled"
    }


@app.post("/", tags=["Root"])
async def root_post(request: Request, background_tasks: BackgroundTasks):
    """
    POST обработчик для корневого пути.
    Может обрабатывать как обычные запросы, так и Telegram webhook.
    """
    logger.info("🔔 ROOT: Получен POST запрос на корневой путь")
    
    try:
        # Пытаемся обработать как Telegram webhook
        update_data = await request.json()
        logger.info(f"📦 ROOT: Данные получены: {update_data}")
        
        # Проверяем, что это Telegram update
        if "message" in update_data or "callback_query" in update_data:
            logger.info("✅ ROOT: Обнаружен Telegram update")
            update = Update.model_validate(update_data)
            background_tasks.add_task(process_telegram_update, update)
            logger.info("🚀 ROOT: Задача обработки добавлена в фоновую очередь")
            return {"status": "ok"}
        else:
            logger.info("ℹ️ ROOT: Это не Telegram update, возвращаем обычный ответ")
            # Если это не Telegram update, возвращаем обычный ответ
            return {
                "status": "OK", 
                "message": "Beauty Salon AI Assistant is running",
                "version": "0.1.0",
                "database": "enabled"
            }
    except Exception as e:
        logger.error(f"❌ ROOT: Ошибка обработки POST запроса: {e}")
        # В случае ошибки возвращаем обычный ответ
        return {
            "status": "OK", 
            "message": "Beauty Salon AI Assistant is running",
            "version": "0.1.0",
            "database": "enabled"
        }


@app.get("/healthcheck", tags=["Health Check"])
def health_check():
    """Простой эндпоинт для проверки работоспособности сервиса."""
    return {
        "status": "OK",
        "database": "enabled",
        "webhook": "enabled"
    }
