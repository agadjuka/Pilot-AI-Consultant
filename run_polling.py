from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

import asyncio
from app.services.telegram_service import telegram_service
from app.api.telegram import process_telegram_update
from app.utils.debug_logger import gemini_debug_logger


async def run_polling():
    """
    Запускает бота в режиме Long Polling для локальной разработки.
    В этом режиме бот сам опрашивает Telegram API на наличие новых сообщений.
    """
    print("\n" + "="*60)
    print("   🤖 Бот запущен в режиме Polling")
    print("="*60)
    
    # Очищаем папку с debug логами при каждом запуске
    gemini_debug_logger.clear_debug_logs()
    
    print("="*60)
    print("   🔄 Удаление webhook...")
    print("="*60)
    
    # Удаляем webhook, если он был установлен
    # Telegram не позволяет одновременно использовать webhook и polling
    webhook_deleted = await telegram_service.delete_webhook()
    if webhook_deleted:
        print("   ✅ Webhook удален")
    else:
        print("   ⚠️  Ошибка при удалении webhook")
    
    print("   ⏳ Ожидание сообщений...")
    print("="*60 + "\n")
    
    offset = 0
    
    while True:
        try:
            # Получаем новые обновления от Telegram
            updates = await telegram_service.get_updates(offset)
            
            if updates:
                print(f"📩 Получено обновлений: {len(updates)}")
                
                # Обрабатываем каждое обновление
                for update in updates:
                    print(f"   ⚙️  Обработка update_id: {update.update_id}")
                    
                    # Переиспользуем существующую логику обработки
                    await process_telegram_update(update)
                    
                    # Обновляем offset, чтобы не получать это сообщение снова
                    offset = update.update_id + 1
                
                print(f"✅ Все обновления обработаны\n")
                
        except KeyboardInterrupt:
            print("\n" + "="*60)
            print("   🛑 Остановка бота...")
            print("="*60 + "\n")
            break
        except Exception as e:
            print(f"❌ Ошибка в polling loop: {e}")
            # Небольшая пауза перед следующей попыткой
            await asyncio.sleep(3)


if __name__ == "__main__":
    try:
        asyncio.run(run_polling())
    except KeyboardInterrupt:
        print("Бот остановлен пользователем")

