"""
Тестовый скрипт для проверки работы debug логгера.
"""
import asyncio
from app.utils.debug_logger import gemini_debug_logger


async def test_debug_logger():
    """Тестирует работу логгера."""
    print("\n" + "="*60)
    print("   🧪 Тест Debug Логгера")
    print("="*60)
    
    # Очищаем папку с логами
    gemini_debug_logger.clear_debug_logs()
    
    # Тестовые данные
    system_instruction = "Ты — Кэт, AI-ассистент салона красоты."
    
    dialog_history = [
        {"role": "user", "text": "Привет! Хочу записаться на маникюр"},
        {"role": "model", "text": "Привет! С удовольствием помогу с записью. Когда вам удобно?"},
        {"role": "user", "text": "Завтра в 15:00"}
    ]
    
    user_message = "А сколько это будет стоить?"
    
    # Логируем запрос
    print("\n📝 Логируем тестовый запрос...")
    request_num = gemini_debug_logger.log_request(
        user_message=user_message,
        dialog_history=dialog_history,
        system_instruction=system_instruction
    )
    
    # Имитируем ответ от Gemini
    await asyncio.sleep(0.5)
    
    response_text = """Стоимость маникюра зависит от типа покрытия:
- Обычный маникюр: 1000 руб
- Гель-лак: 1500 руб
- Наращивание: 2500 руб

Какой вариант вас интересует? 💅"""
    
    # Логируем ответ
    print("\n💬 Логируем тестовый ответ...")
    gemini_debug_logger.log_response(request_num, response_text)
    
    print("\n" + "="*60)
    print("   ✅ Тест завершен!")
    print("   📁 Проверьте папку debug_logs/")
    print("="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(test_debug_logger())

