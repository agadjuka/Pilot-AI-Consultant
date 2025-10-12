import httpx
from app.core.config import settings

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
                print(f"Error sending message to Telegram: {e.response.text}")
                return False

telegram_service = TelegramService(token=settings.TELEGRAM_BOT_TOKEN)

