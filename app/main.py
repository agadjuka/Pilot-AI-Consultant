from fastapi import FastAPI
from app.core.config import settings
from app.api import telegram
from app.services.dialogue_tracer_service import clear_debug_logs

app = FastAPI(
    title="Beauty Salon AI Assistant",
    version="0.1.0"
)

app.include_router(telegram.router, prefix="/telegram", tags=["Telegram"])


@app.on_event("startup")
async def startup_event():
    """Выполняется при запуске приложения."""
    print("\n" + "="*60)
    print("   🚀 Приложение запускается...")
    print("="*60)
    
    # Очищаем папку с логами при каждом запуске
    clear_debug_logs()
    
    print("="*60)


@app.get("/healthcheck", tags=["Health Check"])
def health_check():
    """Простой эндпоинт для проверки работоспособности сервиса."""
    return {"status": "OK"}

