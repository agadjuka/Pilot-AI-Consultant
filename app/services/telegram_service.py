import httpx
from typing import List
import logging
from app.core.config import settings
from app.schemas.telegram import Update

# Получаем логгер для этого модуля
logger = logging.getLogger(__name__)

class TelegramService:
    def __init__(self, token: str):
        self.token = token
        self.api_url = f"https://api.telegram.org/bot{self.token}"

    async def send_message(self, chat_id: int, text: str) -> bool:
        """Асинхронно отправляет сообщение пользователю в Telegram."""
        url = f"{self.api_url}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
        }
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                return True
            except httpx.HTTPStatusError as e:
                logger.error(f"❌ Ошибка отправки сообщения в Telegram: {e.response.text}")
                return False

    async def delete_webhook(self) -> bool:
        """
        Удаляет webhook для перехода в режим long polling.
        Telegram не позволяет одновременно использовать webhook и polling.
        
        Returns:
            True если webhook успешно удален, False в случае ошибки
        """
        url = f"{self.api_url}/deleteWebhook"
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.post(url)
                response.raise_for_status()
                data = response.json()
                return data.get("ok", False)
            except Exception as e:
                logger.error(f"❌ Ошибка удаления webhook: {e}")
                return False

    async def get_updates(self, offset: int = 0) -> List[Update]:
        """
        Получает новые обновления от Telegram через Long Polling.
        
        Args:
            offset: ID последнего обработанного обновления + 1
            
        Returns:
            Список объектов Update
        """
        url = f"{self.api_url}/getUpdates"
        params = {
            "offset": offset,
            "timeout": 30,  # Long polling timeout
        }
        async with httpx.AsyncClient(timeout=35.0) as client:
            try:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                
                if data.get("ok"):
                    updates = [Update.model_validate(update) for update in data.get("result", [])]
                    return updates
                else:
                    logger.error(f"❌ Ошибка получения обновлений: {data}")
                    return []
            except httpx.HTTPError as e:
                logger.error(f"❌ HTTP ошибка получения обновлений: {e}")
                return []
            except Exception as e:
                logger.error(f"❌ Неожиданная ошибка получения обновлений: {e}")
                return []

telegram_service = TelegramService(token=settings.TELEGRAM_BOT_TOKEN)

