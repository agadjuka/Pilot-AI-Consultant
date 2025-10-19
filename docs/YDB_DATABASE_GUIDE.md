# Документация по работе с Yandex Database (YDB)

## Обзор

Проект использует Yandex Database (YDB) для хранения данных. Все таблицы созданы и данные перенесены из SQLite.

## Структура базы данных

### Таблицы

1. **services** - Услуги салона красоты
   - `id` (Int32) - Уникальный идентификатор
   - `name` (String) - Название услуги
   - `description` (Text) - Описание услуги
   - `price` (Double) - Цена услуги
   - `duration_minutes` (Int32) - Длительность в минутах

2. **masters** - Мастера салона
   - `id` (Int32) - Уникальный идентификатор
   - `name` (String) - Имя мастера
   - `specialization` (String) - Специализация

3. **clients** - Клиенты салона
   - `id` (Int32) - Уникальный идентификатор
   - `telegram_id` (Int64) - ID в Telegram
   - `first_name` (String) - Имя клиента
   - `phone_number` (String) - Номер телефона

4. **master_services** - Связь мастеров и услуг
   - `master_id` (Int32) - ID мастера
   - `service_id` (Int32) - ID услуги

5. **appointments** - Записи на услуги
   - `id` (Int32) - Уникальный идентификатор
   - `user_telegram_id` (Int64) - ID пользователя в Telegram
   - `master_id` (Int32) - ID мастера
   - `service_id` (Int32) - ID услуги
   - `start_time` (Timestamp) - Время начала
   - `end_time` (Timestamp) - Время окончания

6. **dialog_history** - История диалогов
   - `id` (Int32) - Уникальный идентификатор
   - `user_id` (Int64) - ID пользователя
   - `role` (String) - Роль (user/model)
   - `message_text` (Text) - Текст сообщения
   - `timestamp` (Timestamp) - Время сообщения

## Подключение к базе данных

### Переменные окружения

В файле `.env` должны быть указаны:

```env
YDB_ENDPOINT=grpcs://ydb.serverless.yandexcloud.net:2135
YDB_DATABASE=/ru-central1/b1gogvdsgf3hje2flr3i/etnci59p991a6s9vd1g4
YC_SERVICE_ACCOUNT_KEY_FILE=key.json
```

### Код подключения

```python
import ydb
import os
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# Получаем настройки
endpoint = os.getenv("YDB_ENDPOINT")
database = os.getenv("YDB_DATABASE")
service_account_key_file = os.getenv("YC_SERVICE_ACCOUNT_KEY_FILE", "key.json")

# Проверяем файл ключа
key_file_path = service_account_key_file
if not os.path.exists(key_file_path):
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    key_file_path = os.path.join(project_root, service_account_key_file)

# Создаем драйвер YDB
driver_config = ydb.DriverConfig(
    endpoint=endpoint,
    database=database,
    credentials=ydb.iam.ServiceAccountCredentials.from_file(key_file_path),
)

# Используем драйвер
with ydb.Driver(driver_config) as driver:
    driver.wait(timeout=5, fail_fast=True)
    
    with ydb.SessionPool(driver) as pool:
        # Ваш код работы с базой данных
        pass
```

## Выполнение запросов

### SELECT запросы

```python
def get_services(session):
    prepared = session.prepare("SELECT * FROM services")
    result = session.transaction().execute(prepared)
    return result[0].rows

# Использование
pool.retry_operation_sync(get_services)
```

### INSERT/UPSERT запросы

```python
def insert_service(session, service_data):
    tx = session.transaction()
    try:
        query = f"""
            UPSERT INTO services (id, name, description, price, duration_minutes)
            VALUES ({service_data['id']}, '{service_data['name']}', '{service_data['description']}', {service_data['price']}, {service_data['duration']})
        """
        prepared = session.prepare(query)
        tx.execute(prepared)
        tx.commit()
    except Exception as e:
        tx.rollback()
        raise e

# Использование
pool.retry_operation_sync(insert_service, service_data)
```

### UPDATE запросы

```python
def update_service(session, service_id, new_price):
    tx = session.transaction()
    try:
        query = f"""
            UPDATE services 
            SET price = {new_price}
            WHERE id = {service_id}
        """
        prepared = session.prepare(query)
        tx.execute(prepared)
        tx.commit()
    except Exception as e:
        tx.rollback()
        raise e
```

### DELETE запросы

```python
def delete_service(session, service_id):
    tx = session.transaction()
    try:
        query = f"DELETE FROM services WHERE id = {service_id}"
        prepared = session.prepare(query)
        tx.execute(prepared)
        tx.commit()
    except Exception as e:
        tx.rollback()
        raise e
```

## Важные особенности YDB

1. **Транзакции** - Всегда используйте явный коммит транзакций
2. **Типы данных** - Строго соблюдайте типы данных (Timestamp, Int32, Int64, String, Text)
3. **Экранирование** - Экранируйте одинарные кавычки в строках: `string.replace("'", "''")`
4. **Подготовленные запросы** - Всегда используйте `session.prepare()` для запросов
5. **Обработка ошибок** - Используйте try/catch с rollback при ошибках

## Статус миграции

✅ **Успешно перенесено:**
- services: 13 записей
- masters: 10 записей  
- clients: 6 записей
- master_services: 58 записей

❌ **Требует внимания:**
- dialog_history: 0 записей (проблема с форматом Timestamp)
- appointments: 0 записей (таблица была пустая в SQLite)

## Полезные команды

### Проверка подключения
```python
python -c "
import ydb
from dotenv import load_dotenv
import os

load_dotenv()
driver_config = ydb.DriverConfig(
    endpoint=os.getenv('YDB_ENDPOINT'),
    database=os.getenv('YDB_DATABASE'),
    credentials=ydb.iam.ServiceAccountCredentials.from_file('key.json'),
)
with ydb.Driver(driver_config) as driver:
    driver.wait(timeout=5, fail_fast=True)
    print('✅ Подключение к YDB успешно!')
"
```

### Подсчет записей в таблице
```python
def count_records(table_name):
    with ydb.Driver(driver_config) as driver:
        driver.wait(timeout=5, fail_fast=True)
        with ydb.SessionPool(driver) as pool:
            def count(session):
                prepared = session.prepare(f"SELECT COUNT(*) as count FROM {table_name}")
                result = session.transaction().execute(prepared)
                return result[0].rows[0][0]
            return pool.retry_operation_sync(count)
```
