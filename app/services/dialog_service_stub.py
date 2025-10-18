"""
Временная заглушка для DialogService без базы данных.
Используется для тестирования webhook'ов когда БД не настроена.
"""
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


class DialogServiceStub:
    """
    Заглушка DialogService для работы без базы данных.
    Возвращает простые ответы для тестирования webhook'ов.
    """
    
    def __init__(self, db_session=None):
        """
        Инициализация заглушки.
        db_session игнорируется для совместимости с оригинальным API.
        """
        logger.info("🔧 STUB: DialogServiceStub инициализирован (режим без БД)")
        self.db_session = db_session
    
    async def process_user_message(self, user_id: int, text: str) -> str:
        """
        Обрабатывает сообщение пользователя и возвращает простой ответ.
        
        Args:
            user_id: ID пользователя Telegram
            text: Текст сообщения пользователя
            
        Returns:
            Простой ответ бота
        """
        logger.info("🎯 STUB: Обработка сообщения пользователя")
        logger.info(f"👤 STUB: Пользователь ID: {user_id}")
        logger.info(f"💬 STUB: Сообщение: '{text}'")
        
        # Простая логика ответов
        text_lower = text.lower().strip()
        
        if text_lower == "/start":
            response = (
                "👋 Привет! Я AI-консультант салона красоты!\n\n"
                "✨ Я помогу вам:\n"
                "• Записаться на процедуры\n"
                "• Узнать о наших услугах\n"
                "• Найти свободное время\n\n"
                "Просто напишите, что вас интересует!"
            )
        elif text_lower == "/clear":
            response = "🧹 История диалога очищена! (режим заглушки)"
        elif "привет" in text_lower or "здравствуй" in text_lower:
            response = "👋 Привет! Как дела? Чем могу помочь?"
        elif "записаться" in text_lower or "запись" in text_lower:
            response = (
                "📅 Отлично! Хотите записаться на процедуру?\n\n"
                "К сожалению, сейчас я работаю в тестовом режиме.\n"
                "База данных временно недоступна, но webhook работает! 🎉"
            )
        elif "услуги" in text_lower or "процедуры" in text_lower:
            response = (
                "💅 Наши услуги:\n\n"
                "• Маникюр и педикюр\n"
                "• Стрижки и укладки\n"
                "• Макияж\n"
                "• Массаж\n\n"
                "В тестовом режиме - webhook работает! ✅"
            )
        elif "время" in text_lower or "расписание" in text_lower:
            response = (
                "🕐 Рабочие часы:\n\n"
                "Пн-Пт: 9:00 - 21:00\n"
                "Сб-Вс: 10:00 - 20:00\n\n"
                "Webhook тестируется успешно! 🚀"
            )
        else:
            response = (
                f"🤖 Получил ваше сообщение: '{text}'\n\n"
                "✅ Webhook работает!\n"
                "🔧 База данных временно отключена\n"
                "📱 Сообщения доставляются корректно\n\n"
                "Попробуйте команды: /start, /clear"
            )
        
        logger.info(f"📤 STUB: Отправляем ответ: '{response[:50]}...'")
        return response
    
    def clear_history(self, user_id: int) -> int:
        """
        Заглушка для очистки истории.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Количество "удаленных" записей (всегда 0 в заглушке)
        """
        logger.info(f"🧹 STUB: Очистка истории для пользователя {user_id}")
        return 0
