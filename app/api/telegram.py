from fastapi import APIRouter, Request
import logging
from app.schemas.telegram import Update
from app.services.telegram_service import telegram_service
from app.services.dialog_service import DialogService
from app.core.config import settings

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
        
        try:
            # Создаем экземпляр DialogService
            dialog_service = DialogService()
            
            # Проверяем, является ли сообщение командой /clear
            if text.strip().lower() == "/clear":
                # Очищаем историю диалога пользователя
                logger.debug(f"--- Вызов clear_history для user_id={user_id}...")
                deleted_count = dialog_service.clear_history(user_id)
                logger.debug(f"--- clear_history завершен. Удалено {deleted_count} записей.")
                
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


@router.post(f"/{settings.TELEGRAM_BOT_TOKEN}", include_in_schema=False)
async def telegram_webhook(request: Request):
    """
    Основной эндпоинт для приема вебхуков от Telegram.
    Вся обработка выполняется синхронно в рамках запроса.
    """
    try:
        logger.info("--- [WEBHOOK START] Получен новый запрос от Telegram.")
        update_data = await request.json()
        update = Update.model_validate(update_data)
        # Прямой вызов и ожидание завершения всей обработки
        logger.info("--- [WEBHOOK] Начинаю полную обработку сообщения (await)...")
        await process_telegram_update(update)
        logger.info("--- [WEBHOOK] Полная обработка сообщения ЗАВЕРШЕНА.")
        logger.info("--- [WEBHOOK END] Отправляю 200 OK в Telegram.")
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"❌ Ошибка в webhook: {e}")
        return {"status": "error", "message": str(e)}


@router.post("/webhook", include_in_schema=False)
async def telegram_webhook_generic(request: Request):
    """
    Универсальный эндпоинт для приема вебхуков от Telegram.
    Вся обработка выполняется синхронно в рамках запроса.
    """
    try:
        logger.info("--- [WEBHOOK START] Получен новый запрос от Telegram.")
        update_data = await request.json()
        update = Update.model_validate(update_data)
        # Прямой вызов и ожидание завершения всей обработки
        logger.info("--- [WEBHOOK] Начинаю полную обработку сообщения (await)...")
        await process_telegram_update(update)
        logger.info("--- [WEBHOOK] Полная обработка сообщения ЗАВЕРШЕНА.")
        logger.info("--- [WEBHOOK END] Отправляю 200 OK в Telegram.")
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"❌ Ошибка обработки webhook: {e}")
        return {"status": "error", "message": str(e)}
