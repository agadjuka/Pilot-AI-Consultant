from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

import asyncio
from app.services.telegram_service import telegram_service
from app.api.telegram import process_telegram_update
from app.utils.debug_logger import gemini_debug_logger

# === ВРЕМЕННЫЙ ТЕСТОВЫЙ БЛОК ДЛЯ ПРОВЕРКИ ToolService ===
from app.core.database import get_session_local
from app.repositories.service_repository import ServiceRepository
from app.repositories.master_repository import MasterRepository
from app.services.tool_service import ToolService

print("\n" + "="*60)
print("   🔧 ТЕСТИРОВАНИЕ ToolService")
print("="*60)

# Создаем сессию БД
SessionLocal = get_session_local()
db = SessionLocal()

try:
    # Инициализируем репозитории
    service_repo = ServiceRepository(db)
    master_repo = MasterRepository(db)
    
    # Создаем экземпляр ToolService
    tool_service = ToolService(service_repo, master_repo)
    
    # Тест 1: Получение всех услуг
    print("\n📋 Тест 1: Получение всех услуг")
    print("-" * 60)
    services_result = tool_service.get_all_services()
    print(services_result)
    
    # Тест 2: Поиск мастеров для услуги (пример с "Женская стрижка")
    print("\n👥 Тест 2: Поиск мастеров для услуги 'Женская стрижка'")
    print("-" * 60)
    masters_result = tool_service.get_masters_for_service("Женская стрижка")
    print(masters_result)
    
    # Тест 3: Получение свободных слотов (заглушка)
    print("\n⏰ Тест 3: Получение свободных слотов (заглушка)")
    print("-" * 60)
    slots_result = tool_service.get_available_slots("Анна", "2025-10-15")
    print(slots_result)
    
    print("\n" + "="*60)
    print("   ✅ Все тесты ToolService завершены")
    print("="*60 + "\n")
    
finally:
    db.close()

# === КОНЕЦ ТЕСТОВОГО БЛОКА ===


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

