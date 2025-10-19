# Документация проекта

## Файлы документации

### 📊 [YDB_DATABASE_GUIDE.md](./YDB_DATABASE_GUIDE.md)
Полное руководство по работе с Yandex Database (YDB):
- Структура базы данных
- Подключение к YDB
- Выполнение запросов
- Статус миграции данных
- Полезные команды

### 🔧 [YDB_CHANGES_GUIDE.md](./YDB_CHANGES_GUIDE.md)
Руководство по внесению изменений в YDB:
- Добавление новых записей
- Обновление существующих данных
- Удаление записей
- Получение данных
- Примеры использования
- Обработка ошибок

## Быстрый старт

1. **Проверка подключения:**
   ```bash
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

2. **Подсчет записей в таблице:**
   ```python
   from app.core.database import get_engine
   # Используйте функции из YDB_CHANGES_GUIDE.md
   ```

## Статус проекта

✅ **Готово:**
- Миграция данных из SQLite в YDB
- Создание таблиц в YDB
- Документация по работе с базой данных
- Очистка проекта от тестовых файлов

📝 **Требует внимания:**
- Обновление `app/core/database.py` для работы с чистым YDB драйвером
- Исправление проблемы с `dialog_history` (формат Timestamp)

## Контакты

При возникновении вопросов по работе с YDB обращайтесь к документации или создавайте issue в проекте.
