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
    if update.message and update.message.text:
        chat_id = update.message.chat.id
        user_id = update.message.from_user.id if update.message.from_user else chat_id
        text = update.message.text
        
        # Создаем сессию базы данных для обработки сообщения
        SessionLocal = get_session_local()
        db: Session = SessionLocal()
        
        try:
            # Создаем экземпляр DialogService с сессией БД
            dialog_service = DialogService(db)
            
            # Проверяем, является ли сообщение командой /clear
            if text.strip().lower() == "/clear":
                # Очищаем историю диалога пользователя
                deleted_count = dialog_service.clear_history(user_id)
                
                # Отправляем подтверждение
                confirmation_message = (
                    "✨ История диалога успешно очищена!\n\n"
                    "Теперь вы можете начать новый разговор с чистого листа."
                )
                await telegram_service.send_message(chat_id, confirmation_message)
            else:
                # Обрабатываем обычное сообщение пользователя и получаем ответ от AI
                bot_response = await dialog_service.process_user_message(user_id, text)
                
                # Отправляем ответ пользователю
                await telegram_service.send_message(chat_id, bot_response)
                
        except Exception as e:
            logger.error(f"❌ Ошибка обработки сообщения: {e}", exc_info=True)
            # В случае ошибки отправляем пользователю дружелюбное сообщение
            error_message = "Извините, произошла ошибка при обработке вашего сообщения. Пожалуйста, попробуйте еще раз."
            await telegram_service.send_message(chat_id, error_message)
        finally:
            # Всегда закрываем сессию БД
            db.close()


@router.post(f"/{settings.TELEGRAM_BOT_TOKEN}", include_in_schema=False)
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Основной эндпоинт для приема вебхуков от Telegram.
    Мы используем BackgroundTasks, чтобы немедленно вернуть Telegram статус 200 OK,
    а обработку сообщения выполнить в фоновом режиме.
    """
    try:
        update_data = await request.json()
        update = Update.parse_obj(update_data)
        background_tasks.add_task(process_telegram_update, update)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"❌ Ошибка в webhook: {e}")
        return {"status": "error", "message": str(e)}


@router.post("/webhook", include_in_schema=False)
async def telegram_webhook_generic(request: Request, background_tasks: BackgroundTasks):
    """
    Универсальный эндпоинт для приема вебхуков от Telegram.
    Используется когда Telegram настроен на отправку на /telegram/webhook
    """
    try:
        update_data = await request.json()
        update = Update.parse_obj(update_data)
        background_tasks.add_task(process_telegram_update, update)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"❌ Ошибка обработки webhook: {e}")
        return {"status": "error", "message": str(e)}
