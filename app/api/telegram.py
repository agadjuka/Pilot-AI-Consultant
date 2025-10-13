from fastapi import APIRouter, Request, BackgroundTasks
from sqlalchemy.orm import Session
from app.schemas.telegram import Update
from app.services.telegram_service import telegram_service
from app.services.dialog_service import DialogService
from app.core.config import settings
from app.core.database import get_session_local

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
            
            # Обрабатываем сообщение пользователя и получаем ответ от AI
            bot_response = await dialog_service.process_user_message(user_id, text)
            
            # Отправляем ответ пользователю
            await telegram_service.send_message(chat_id, bot_response)
        except Exception as e:
            # В случае ошибки отправляем пользователю дружелюбное сообщение
            error_message = "Извините, произошла ошибка при обработке вашего сообщения. Пожалуйста, попробуйте еще раз."
            await telegram_service.send_message(chat_id, error_message)
            # Логируем ошибку для отладки
            print(f"Error processing message: {e}")
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
    update_data = await request.json()
    update = Update.model_validate(update_data)
    background_tasks.add_task(process_telegram_update, update)
    return {"status": "ok"}

