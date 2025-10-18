# Инструкция по настройке Telegram Webhook в Yandex Cloud

## Проблема
В логах видно ошибку `404 Not Found` при POST запросе на корневой путь `/`. Это происходит потому, что Yandex Cloud отправляет запросы на неправильный URL.

## Решение

### 1. Правильный URL для Telegram Webhook
Ваш Telegram webhook должен быть доступен по адресу:
```
https://your-function-url/telegram/{TELEGRAM_BOT_TOKEN}
```

Где:
- `your-function-url` - URL вашей функции в Yandex Cloud
- `{TELEGRAM_BOT_TOKEN}` - токен вашего бота из переменной окружения

### 2. Настройка в Yandex Cloud
В консоли Yandex Cloud нужно настроить триггер так, чтобы он отправлял запросы на правильный путь:

1. **Откройте консоль Yandex Cloud**
2. **Перейдите в раздел "Serverless Functions"**
3. **Найдите вашу функцию**
4. **Перейдите в "Триггеры"**
5. **Настройте HTTP-триггер с правильным путем**

### 3. Альтернативное решение
Если вы хотите, чтобы корневой путь `/` обрабатывал Telegram webhook, можно изменить код:

```python
# В app/main.py добавить:
@app.post("/", tags=["Root"])
async def root_post(request: Request, background_tasks: BackgroundTasks):
    """POST обработчик для корневого пути (Telegram webhook)."""
    try:
        update_data = await request.json()
        update = Update.model_validate(update_data)
        background_tasks.add_task(process_telegram_update, update)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Ошибка обработки Telegram webhook: {e}")
        return {"status": "error", "message": str(e)}
```

### 4. Проверка
После настройки проверьте:
1. **Корневой путь** `/` - должен возвращать статус OK
2. **Telegram webhook** `/telegram/{TOKEN}` - должен обрабатывать сообщения
3. **Healthcheck** `/healthcheck` - должен возвращать статус OK

## Текущие эндпоинты
- `GET /` - корневой эндпоинт (статус OK)
- `POST /` - корневой POST эндпоинт (статус OK) 
- `GET /healthcheck` - проверка работоспособности
- `POST /telegram/{TOKEN}` - Telegram webhook
- `GET /docs` - Swagger UI документация
- `GET /openapi.json` - OpenAPI спецификация
