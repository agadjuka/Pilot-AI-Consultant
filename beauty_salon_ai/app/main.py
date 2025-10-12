from fastapi import FastAPI
from app.core.config import settings
from app.api import telegram

app = FastAPI(
    title="Beauty Salon AI Assistant",
    version="0.1.0"
)

app.include_router(telegram.router, prefix="/telegram", tags=["Telegram"])

@app.get("/healthcheck", tags=["Health Check"])
def health_check():
    """Простой эндпоинт для проверки работоспособности сервиса."""
    return {"status": "OK"}

