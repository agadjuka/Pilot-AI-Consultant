from fastapi import APIRouter, Request, BackgroundTasks
from sqlalchemy.orm import Session
import logging
from app.schemas.telegram import Update
from app.services.telegram_service import telegram_service
from app.services.dialog_service import DialogService
from app.core.config import settings
from app.core.database import get_session_local

# Получаем логгер для этого модуля
logger = logging.getLogger(__name__)

router = APIRouter()


async def process_telegram_update(update: Update):
    """
    Обрабатывает входящее обновление от Telegram.
    Использует DialogService для генерации интеллектуального ответа.
    """
    logger.info("🔄 PROCESS: Начало обработки Telegram update")
    logger.info(f"📋 PROCESS: Update ID: {update.update_id}")
    
    if update.message and update.message.text:
        chat_id = update.message.chat.id
        user_id = update.message.from_user.id if update.message.from_user else chat_id
        text = update.message.text
        
        logger.info(f"💬 PROCESS: Сообщение от пользователя {user_id} в чате {chat_id}")
        logger.info(f"📝 PROCESS: Текст сообщения: '{text}'")
        
        # Создаем сессию базы данных для обработки сообщения
        SessionLocal = get_session_local()
        db: Session = SessionLocal()
        logger.info("🗄️ PROCESS: Сессия БД создана")
        
        try:
            # Создаем экземпляр DialogService с сессией БД
            dialog_service = DialogService(db)
            logger.info("🤖 PROCESS: DialogService создан")
            
            # Проверяем, является ли сообщение командой /clear
            if text.strip().lower() == "/clear":
                logger.info("🧹 PROCESS: Обнаружена команда /clear")
                # Очищаем историю диалога пользователя
                deleted_count = dialog_service.clear_history(user_id)
                logger.info(f"🗑️ PROCESS: Удалено {deleted_count} записей истории")
                
                # Отправляем подтверждение
                confirmation_message = (
                    "✨ История диалога успешно очищена!\n\n"
                    "Теперь вы можете начать новый разговор с чистого листа."
                )
                logger.info("📤 PROCESS: Отправка подтверждения очистки")
                await telegram_service.send_message(chat_id, confirmation_message)
                logger.info("✅ PROCESS: Подтверждение отправлено")
            else:
                logger.info("💭 PROCESS: Обработка обычного сообщения")
                # Обрабатываем обычное сообщение пользователя и получаем ответ от AI
                bot_response = await dialog_service.process_user_message(user_id, text)
                logger.info(f"🤖 PROCESS: Получен ответ от AI: '{bot_response[:100]}...'")
                
                # Отправляем ответ пользователю
                logger.info("📤 PROCESS: Отправка ответа пользователю")
                await telegram_service.send_message(chat_id, bot_response)
                logger.info("✅ PROCESS: Ответ отправлен пользователю")
                
        except Exception as e:
            logger.error("💥 PROCESS: Произошла ошибка при обработке сообщения")
            # В случае ошибки отправляем пользователю дружелюбное сообщение
            error_message = "Извините, произошла ошибка при обработке вашего сообщения. Пожалуйста, попробуйте еще раз."
            logger.info("📤 PROCESS: Отправка сообщения об ошибке пользователю")
            await telegram_service.send_message(chat_id, error_message)
            logger.info("✅ PROCESS: Сообщение об ошибке отправлено")
            
            # Логируем ошибку для отладки с более подробной информацией
            logger.error(f"❌ PROCESS: Ошибка обработки сообщения: {e}")
            logger.error(f"❌ PROCESS: Тип ошибки: {type(e).__name__}")
            import traceback
            logger.error(f"❌ PROCESS: Трассировка: {traceback.format_exc()}")
        finally:
            # Всегда закрываем сессию БД
            db.close()
            logger.info("🔒 PROCESS: Сессия БД закрыта")
    else:
        logger.warning("⚠️ PROCESS: Update не содержит текстового сообщения")
        logger.info(f"📋 PROCESS: Тип update: {type(update).__name__}")
    
    logger.info("🏁 PROCESS: Обработка Telegram update завершена")


@router.post(f"/{settings.TELEGRAM_BOT_TOKEN}", include_in_schema=False)
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Основной эндпоинт для приема вебхуков от Telegram.
    Мы используем BackgroundTasks, чтобы немедленно вернуть Telegram статус 200 OK,
    а обработку сообщения выполнить в фоновом режиме.
    """
    logger.info("🔔 WEBHOOK: Получен запрос на основной эндпоинт")
    try:
        update_data = await request.json()
        logger.info(f"📦 WEBHOOK: Данные получены: {update_data}")
        
        update = Update.parse_obj(update_data)
        logger.info(f"✅ WEBHOOK: Update валидирован успешно")
        
        background_tasks.add_task(process_telegram_update, update)
        logger.info("🚀 WEBHOOK: Задача добавлена в фоновую очередь")
        
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"❌ WEBHOOK: Ошибка в основном эндпоинте: {e}")
        return {"status": "error", "message": str(e)}


@router.post("/webhook", include_in_schema=False)
async def telegram_webhook_generic(request: Request, background_tasks: BackgroundTasks):
    """
    Универсальный эндпоинт для приема вебхуков от Telegram.
    Используется когда Telegram настроен на отправку на /telegram/webhook
    """
    logger.info("🔔 WEBHOOK: Получен запрос на универсальный эндпоинт /webhook")
    try:
        update_data = await request.json()
        logger.info(f"📦 WEBHOOK: Данные получены через /webhook: {update_data}")
        
        update = Update.parse_obj(update_data)
        logger.info(f"✅ WEBHOOK: Update валидирован успешно через /webhook")
        
        background_tasks.add_task(process_telegram_update, update)
        logger.info("🚀 WEBHOOK: Задача добавлена в фоновую очередь через /webhook")
        
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"❌ WEBHOOK: Ошибка обработки webhook через /webhook: {e}")
        return {"status": "error", "message": str(e)}
