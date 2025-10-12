from fastapi import FastAPI
from app.core.config import settings # Импортируем наш объект настроек

# Создаем экземпляр приложения FastAPI
app = FastAPI(
    title="Beauty Salon AI Assistant",
    version="0.1.0"
)

@app.get("/healthcheck", tags=["Health Check"])
def health_check():
    """
    Простой эндпоинт для проверки работоспособности сервиса.
    """
    return {"status": "OK"}

# Пример использования настроек (пока закомментирован, но показывает как это работает)
# print(f"Loaded DATABASE_URL: {settings.DATABASE_URL}")

