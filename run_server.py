import uvicorn
import logging

# Получаем логгер для этого модуля
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    logger.info("╔═══════════════════════════════════════════════════════════")
    logger.info("║ 🚀 Сервер для Webhook запущен")
    logger.info("╚═══════════════════════════════════════════════════════════")
    logger.info(f"📍 URL:         http://127.0.0.1:8001")
    logger.info(f"💚 Healthcheck: http://127.0.0.1:8001/healthcheck")
    logger.info("ℹ️  Этот режим предназначен для продакшена.")
    logger.info("ℹ️  Для локальной разработки используйте: python run_polling.py")
    
    uvicorn.run("app.main:app", host="127.0.0.1", port=8001, reload=True)

