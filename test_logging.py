#!/usr/bin/env python3
"""
Тестовый скрипт для проверки системы логирования.
"""

import asyncio
from app.core.database import get_db_session
from app.services.dialog_service import DialogService

async def test_logging():
    """Тестирует систему логирования."""
    print("🧪 Тестирование системы логирования...")
    
    # Получаем сессию базы данных
    db_session = next(get_db_session())
    
    try:
        # Создаем сервис диалога
        dialog_service = DialogService(db_session)
        
        # Тестируем обработку сообщения
        test_user_id = 999999999  # Тестовый ID пользователя
        test_message = "Здравствуйте, сколько стоит маникюр?"
        
        print(f"📝 Отправляем тестовое сообщение: {test_message}")
        
        # Обрабатываем сообщение
        response = await dialog_service.process_user_message(test_user_id, test_message)
        
        print(f"✅ Получен ответ: {response}")
        print("🎉 Тест завершен! Проверьте папку debug_logs для новых файлов.")
        
    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        db_session.close()

if __name__ == "__main__":
    asyncio.run(test_logging())
