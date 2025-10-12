from fastapi import APIRouter, Request, BackgroundTasks
from app.schemas.telegram import Update
from app.services.telegram_service import telegram_service
from app.core.config import settings

router = APIRouter()

async def process_telegram_update(update: Update):
    """Обрабатывает входящее обновление от Telegram."""
    if update.message and update.message.text:
        chat_id = update.message.chat.id
        text = update.message.text
        await telegram_service.send_message(chat_id, f"Вы написали: {text}")

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

