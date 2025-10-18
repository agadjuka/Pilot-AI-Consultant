"""
Модифицированная версия Telegram API с заглушками для работы без БД.
Используется для тестирования webhook'ов когда БД не настроена.
"""
from fastapi import APIRouter, Request, BackgroundTasks
import logging
from app.schemas.telegram import Update
from app.services.telegram_service import telegram_service
from app.services.dialog_service_stub import DialogServiceStub
from app.core.config import settings

# Получаем логгер для этого модуля
logger = logging.getLogger(__name__)

router = APIRouter()


async def process_telegram_update_stub(update: Update):
    """
    Обрабатывает входящее обновление от Telegram с использованием заглушек.
    Работает без базы данных для тестирования webhook'ов.
    """
    logger.info("🔄 STUB: Начало обработки Telegram update (режим заглушки)")
    logger.info(f"📋 STUB: Update ID: {update.update_id}")
    
    if update.message and update.message.text:
        chat_id = update.message.chat.id
        user_id = update.message.from_user.id if update.message.from_user else chat_id
        text = update.message.text
        
        logger.info(f"💬 STUB: Сообщение от пользователя {user_id} в чате {chat_id}")
        logger.info(f"📝 STUB: Текст сообщения: '{text}'")
        
        try:
            # Создаем экземпляр DialogServiceStub (без БД)
            dialog_service = DialogServiceStub()
            logger.info("🤖 STUB: DialogServiceStub создан")
            
            # Проверяем, является ли сообщение командой /clear
            if text.strip().lower() == "/clear":
                logger.info("🧹 STUB: Обнаружена команда /clear")
                # Очищаем историю диалога пользователя (заглушка)
                deleted_count = dialog_service.clear_history(user_id)
                logger.info(f"🗑️ STUB: Удалено {deleted_count} записей истории (заглушка)")
                
                # Отправляем подтверждение
                confirmation_message = (
                    "✨ История диалога успешно очищена!\n\n"
                    "🔧 Работаем в тестовом режиме без БД\n"
                    "✅ Webhook работает корректно!"
                )
                logger.info("📤 STUB: Отправка подтверждения очистки")
                await telegram_service.send_message(chat_id, confirmation_message)
                logger.info("✅ STUB: Подтверждение отправлено")
            else:
                logger.info("💭 STUB: Обработка обычного сообщения")
                # Обрабатываем обычное сообщение пользователя и получаем ответ от заглушки
                bot_response = await dialog_service.process_user_message(user_id, text)
                logger.info(f"🤖 STUB: Получен ответ от заглушки: '{bot_response[:100]}...'")
                
                # Отправляем ответ пользователю
                logger.info("📤 STUB: Отправка ответа пользователю")
                await telegram_service.send_message(chat_id, bot_response)
                logger.info("✅ STUB: Ответ отправлен пользователю")
                
        except Exception as e:
            logger.error("💥 STUB: Произошла ошибка при обработке сообщения")
            # В случае ошибки отправляем пользователю дружелюбное сообщение
            error_message = (
                "Извините, произошла ошибка при обработке вашего сообщения.\n\n"
                "🔧 Работаем в тестовом режиме\n"
                "✅ Webhook работает, но есть проблемы с обработкой"
            )
            logger.info("📤 STUB: Отправка сообщения об ошибке пользователю")
            await telegram_service.send_message(chat_id, error_message)
            logger.info("✅ STUB: Сообщение об ошибке отправлено")
            
            # Логируем ошибку для отладки с более подробной информацией
            logger.error(f"❌ STUB: Ошибка обработки сообщения: {e}")
            logger.error(f"❌ STUB: Тип ошибки: {type(e).__name__}")
            import traceback
            logger.error(f"❌ STUB: Трассировка: {traceback.format_exc()}")
    else:
        logger.warning("⚠️ STUB: Update не содержит текстового сообщения")
        logger.info(f"📋 STUB: Тип update: {type(update).__name__}")
    
    logger.info("🏁 STUB: Обработка Telegram update завершена")


@router.post(f"/{settings.TELEGRAM_BOT_TOKEN}", include_in_schema=False)
async def telegram_webhook_stub(request: Request, background_tasks: BackgroundTasks):
    """
    Основной эндпоинт для приема вебхуков от Telegram с заглушками.
    Работает без базы данных для тестирования webhook'ов.
    """
    logger.info("🔔 STUB: Получен запрос на основной эндпоинт (режим заглушки)")
    try:
        update_data = await request.json()
        logger.info(f"📦 STUB: Данные получены: {update_data}")
        
        update = Update.parse_obj(update_data)
        logger.info(f"✅ STUB: Update валидирован успешно")
        
        background_tasks.add_task(process_telegram_update_stub, update)
        logger.info("🚀 STUB: Задача добавлена в фоновую очередь")
        
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"❌ STUB: Ошибка в основном эндпоинте: {e}")
        return {"status": "error", "message": str(e)}


@router.post("/webhook", include_in_schema=False)
async def telegram_webhook_generic_stub(request: Request, background_tasks: BackgroundTasks):
    """
    Универсальный эндпоинт для приема вебхуков от Telegram с заглушками.
    Используется когда Telegram настроен на отправку на /telegram/webhook.
    Работает без базы данных для тестирования webhook'ов.
    """
    logger.info("🔔 STUB: Получен запрос на универсальный эндпоинт /webhook (режим заглушки)")
    try:
        update_data = await request.json()
        logger.info(f"📦 STUB: Данные получены через /webhook: {update_data}")
        
        update = Update.parse_obj(update_data)
        logger.info(f"✅ STUB: Update валидирован успешно через /webhook")
        
        background_tasks.add_task(process_telegram_update_stub, update)
        logger.info("🚀 STUB: Задача добавлена в фоновую очередь через /webhook")
        
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"❌ STUB: Ошибка обработки webhook через /webhook: {e}")
        return {"status": "error", "message": str(e)}
