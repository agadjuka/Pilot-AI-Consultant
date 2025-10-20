## Аудит асинхронной архитектуры

Дата: 2025-10-20

### 1) Точка входа (обработчик вебхука)

- Эндпоинт принимает POST запросы от Telegram и немедленно возвращает 200 OK, передавая обработку в фон через BackgroundTasks.
- Функция `process_telegram_update` является асинхронной и внутри использует `await` для сервисов.

```python
# app/api/telegram.py (фрагмент)
from fastapi import APIRouter, Request, BackgroundTasks
import logging
from app.schemas.telegram import Update
from app.services.telegram_service import telegram_service
from app.services.dialog_service import DialogService
from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

async def process_telegram_update(update: Update):
    if update.message and update.message.text:
        chat_id = update.message.chat.id
        user_id = update.message.from_user.id if update.message.from_user else chat_id
        text = update.message.text
        try:
            dialog_service = DialogService()
            if text.strip().lower() == "/clear":
                deleted_count = dialog_service.clear_history(user_id)
                confirmation_message = (
                    "✨ История диалога успешно очищена!\n\n"
                    "Теперь вы можете начать новый разговор с чистого листа."
                )
                await telegram_service.send_message(chat_id, confirmation_message)
            else:
                bot_response = await dialog_service.process_user_message(user_id, text)
                await telegram_service.send_message(chat_id, bot_response)
        except Exception as e:
            logger.error(f"❌ Ошибка обработки сообщения: {e}", exc_info=True)
            error_message = "Извините, произошла ошибка при обработке вашего сообщения. Пожалуйста, попробуйте еще раз."
            await telegram_service.send_message(chat_id, error_message)

@router.post(f"/{settings.TELEGRAM_BOT_TOKEN}", include_in_schema=False)
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
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
    try:
        update_data = await request.json()
        update = Update.parse_obj(update_data)
        background_tasks.add_task(process_telegram_update, update)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"❌ Ошибка обработки webhook: {e}")
        return {"status": "error", "message": str(e)}
```

- Запуск логики: через `BackgroundTasks.add_task(process_telegram_update, update)` — обработка идёт в фоне, эндпоинт не блокируется.

### 2) Основная функция-оркестратор `process_telegram_update`

- Да, это `async def` (см. выше). Внутри:
  - Команда `/clear` — использует синхронный `DialogService.clear_history` (без await).
  - Обычные сообщения — `await dialog_service.process_user_message(...)` и затем `await telegram_service.send_message(...)`.

### 3) Сервис диалога `DialogService`

- Основной метод: `async def process_user_message(self, user_id: int, text: str) -> str` — асинхронный.
- Вызовы внутри:
  - Репозитории/БД: используются синхронно (без `await`), напр. `self.client_repository.get_or_create_by_telegram_id(user_id)`, `self.repository.get_recent_messages(...)`, `self.repository.add_message(...)`.
  - Вызовы LLM: асинхронные — `await self.llm_service.generate_response(...)` (несколько этапов), fallback-генерации также через `await`.
  - Инструменты: через `self.tool_orchestrator.execute_single_tool(...)` — используется `await`.

```python
# app/services/dialog_service.py (фрагмент)
class DialogService:
    CONTEXT_WINDOW_SIZE = 12

    async def process_user_message(self, user_id: int, text: str) -> str:
        # 0. Клиент из БД — СИНХРОННО (блокирует event loop)
        client = self.client_repository.get_or_create_by_telegram_id(user_id)

        # 1. История — СИНХРОННО (блокирует event loop)
        history_records = self.repository.get_recent_messages(user_id, limit=self.CONTEXT_WINDOW_SIZE)

        # 2. Сохранение входящего — СИНХРОННО (блокирует event loop)
        self.repository.add_message(user_id=user_id, role="user", message_text=text)

        # Этап 1: Классификация — АСИНХРОННО
        stage_str = await self.llm_service.generate_response(classification_history, tracer=tracer)

        # Этап 2: Мышление — АСИНХРОННО (LLM) + выполнение инструментов — АСИНХРОННО
        thinking_response = await self.llm_service.generate_response(thinking_history, filtered_tools, tracer=tracer)
        tool_result = await self.tool_orchestrator.execute_single_tool(tool_name, parameters, user_id, dialog_context, tracer)

        # Этап 3: Синтез — АСИНХРОННО (LLM) + инструменты — АСИНХРОННО
        synthesis_response = await self.llm_service.generate_response(synthesis_history, filtered_tools, tracer=tracer)

        # Сохранение финального ответа — СИНХРОННО (блокирует event loop)
        self.repository.add_message(user_id=user_id, role="model", message_text=bot_response_text)
        return bot_response_text

    def clear_history(self, user_id: int) -> int:
        return self.repository.clear_user_history(user_id)
```

Вывод по пункту 3: Внутри асинхронного метода есть множественные синхронные вызовы репозиториев/БД — это потенциальные блокировки event loop под нагрузкой.

### 4) Слой данных (репозитории и `database.py`)

Главный модуль YDB: `app/core/database.py` — все операции реализованы СИНХРОННО и используют `retry_operation_sync(...)`.

```python
# app/core/database.py (фрагменты)
import ydb
...
def get_session_pool() -> ydb.SessionPool:
    driver = get_driver()
    _session_pool = ydb.SessionPool(driver)
    return _session_pool

@contextmanager
def get_db_session():
    pool = get_session_pool()
    def get_session():
        return pool.acquire()
    session = None
    try:
        session = pool.retry_operation_sync(get_session)
        yield session
    finally:
        if session:
            pool.release(session)

def execute_query(query: str, params: Optional[Dict[str, Any]] = None) -> List[Any]:
    pool = get_session_pool()
    def execute(session):
        tx = session.transaction()
        prepared = session.prepare(query)
        result = tx.execute(prepared)
        tx.commit()
        return result[0].rows
    return pool.retry_operation_sync(execute)

def execute_transaction(operations: List[callable]):
    pool = get_session_pool()
    def execute_all(session):
        tx = session.transaction()
        results = []
        for operation in operations:
            result = operation(session, tx)
            results.append(result)
        tx.commit()
        return results
    return pool.retry_operation_sync(execute_all)

def upsert_record(table: str, data: Dict[str, Any]) -> None:
    pool = get_session_pool()
    def upsert(session):
        tx = session.transaction()
        # Формирование UPSERT и выполнение
        prepared = session.prepare(query)
        tx.execute(prepared)
        tx.commit()
    pool.retry_operation_sync(upsert)
```

Статус асинхронности функций слоя данных:
- Все перечисленные функции — объявлены как синхронные (`def`), не `async def`.
- Используют синхронные вызовы драйвера: `pool.retry_operation_sync(...)`.

Пример использования в репозитории (синхронно, без await):

```python
# app/repositories/client_repository.py (фрагмент)
from app.core.database import execute_query, upsert_record

class ClientRepository(BaseRepository):
    def get_by_telegram_id(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        query = f"SELECT * FROM {self.table_name} WHERE telegram_id = {telegram_id}"
        rows = execute_query(query)  # СИНХРОННО
        if rows:
            return self._row_to_dict(rows[0])
        return None

    def get_or_create_by_telegram_id(self, telegram_id: int) -> Dict[str, Any]:
        client = self.get_by_telegram_id(telegram_id)  # СИНХРОННО
        if client:
            return client
        new_id = self.create({ ... })  # create внутри базового репозитория также синхронный
        return self.get_by_id(new_id)  # СИНХРОННО
```

И репозиторий истории диалогов (также синхронный):

```python
# app/repositories/dialog_history_repository.py (фрагмент)
from app.core.database import execute_query, upsert_record, delete_record

class DialogHistoryRepository(BaseRepository):
    def get_recent_messages(self, user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        query = f"""
            SELECT * FROM {self.table_name} 
            WHERE user_id = {user_id}
            ORDER BY timestamp DESC
            LIMIT {limit}
        """
        rows = execute_query(query)  # СИНХРОННО
        return [self._row_to_dict(row) for row in reversed(rows)]

    def add_message(self, user_id: int, role: str, message_text: str) -> Dict[str, Any]:
        # вычисление нового id + upsert_record(...) — СИНХРОННО
        upsert_record(self.table_name, data)
        return self.get_by_id(new_id)
```

Итого по пункту 4: слой данных полностью синхронный; вызывается из асинхронных контекстов без `await` — это главный источник блокировок.

### 5) Сервис отправки в Telegram `TelegramService`

- Метод `send_message` — `async def`, использует `httpx.AsyncClient` и корректно `await` на HTTP запрос.

```python
# app/services/telegram_service.py (фрагмент)
import httpx

class TelegramService:
    async def send_message(self, chat_id: int, text: str) -> bool:
        url = f"{self.api_url}/sendMessage"
        payload = {"chat_id": chat_id, "text": text}
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return True
```

Дополнительно: в `run_polling.py` используется `await telegram_service.get_updates(offset)` — также асинхронно.

### Финальное заключение

Критическая оценка цепочки: от получения запроса до отправки ответа — НЕ полностью неблокирующая.

- Позитивно:
  - Эндпоинт отдаёт ответ сразу, логика выносится в фоновые задачи.
  - `process_telegram_update` и `TelegramService.send_message` — асинхронные.
  - LLM-вызовы и инструменты внутри `DialogService` — с `await`.

- Узкие места (синхронные «бутылочные горлышки»):
  - Слой БД (`app/core/database.py`) целиком синхронный и повсеместно использует `retry_operation_sync(...)`.
  - Репозитории вызывают эти функции синхронно; в `DialogService.process_user_message` они исполняются внутри `async def` без offloading, блокируя event loop.
  - Метод `clear_history` вызывается из вебхука синхронно.

Риск: под нагрузкой длительные обращения к YDB будут блокировать event loop и задерживать обработку других запросов/сообщений (в т.ч. отправку ответов), что проявляется как «зависшие» ответы.

### Рекомендации (кратко)

1) Перевести слой данных на асинхронные вызовы драйвера (`retry_operation` с `await`, либо использовать `asyncio.to_thread`/`run_in_executor` как временный костыль вокруг синхронных БД-операций).
2) Репозитории сделать асинхронными (`async def` + `await` внутрь).
3) В `DialogService` везде `await repo.method(...)`, чтобы не блокировать event loop.
4) Для долгих CPU/IO операций без async — вынос в executor.


