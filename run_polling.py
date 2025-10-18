from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

# Настраиваем логирование сразу после загрузки переменных окружения
from app.core.logging_config import setup_logging
setup_logging()

import asyncio
import logging
from app.services.telegram_service import telegram_service
from app.api.telegram import process_telegram_update
from app.services.dialogue_tracer_service import clear_debug_logs

# Получаем логгер для этого модулm
logger = logging.getLogger(__name__)


async def run_polling():
    """
    Запускает бота в режиме Long Polling для локальной разработки.
    В этом режиме бот сам опрашивает Telegram API на наличие новых сообщений.
    """
    logger.info("╔═══════════════════════════════════════════════════════════")
    logger.info("║ 🤖 Бот запущен в режиме Polling")
    logger.info("╚═══════════════════════════════════════════════════════════")
    
    # Очищаем папку с логами при каждом запуске
    clear_debug_logs()
    
    logger.info("🔄 Удаление webhook...")
    
    # Удаляем webhook, если он был установле
    # Telegram не позволяет одновременно использовать webhook и pollin
    webhook_deleted = await telegram_service.delete_webhook()
    if webhook_deleted:
        logger.info("✅ Webhook удален")
    else:
        logger.warning("⚠️ Ошибка при удалении webhook")
    
    logger.info("⏳ Ожидание сообщений...")
    
    offset = 0
    
    while True:
        try:
            # Получаем новые обновления от Telegram
            updates = await telegram_service.get_updates(offset)
            
            if updates:
                logger.info(f"📩 Получено обновлений: {len(updates)}")
                
                # Обрабатываем каждое обновление
                for update in updates:
                    # Переиспользуем существующую логику обработки
                    await process_telegram_update(update)
                    
                    # Обновляем offset, чтобы не получать это сообщение снова
                    offset = update.update_id + 1
                
                logger.info("✅ Все обновления обработаны")
                
        except KeyboardInterrupt:
            logger.info("╔═══════════════════════════════════════════════════════════")
            logger.info("║ 🛑 Остановка бота...")
            logger.info("╚═══════════════════════════════════════════════════════════")
            break
        except Exception as e:
            logger.error(f"❌ Ошибка в polling loop: {e}", exc_info=True)
            # Небольшая пауза перед следующей попыткой
            await asyncio.sleep(3)


if __name__ == "__main__":
    try:
        asyncio.run(run_polling())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")

