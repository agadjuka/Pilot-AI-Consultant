# Система поддержки множественных конфигураций

## Обзор

Проект теперь поддерживает загрузку разных конфигурационных файлов через переменную окружения `ENV_FILE`. Это позволяет легко переключаться между различными средами разработки и тестирования.

## Использование

### 1. Переменная ENV_FILE

Система автоматически определяет, какой `.env` файл загружать:
- Если `ENV_FILE` не установлена → используется `.env` (по умолчанию)
- Если `ENV_FILE=.env.local_cloud` → используется `.env.local_cloud`
- Если `ENV_FILE=.env.test` → используется `.env.test`

### 2. Скрипт "Локальное Облако"

Создан новый скрипт `run_local_cloud.py` для запуска сервера в режиме "локального облака":

```bash
python run_local_cloud.py
```

Этот скрипт:
- Автоматически устанавливает `ENV_FILE=.env.local_cloud`
- Запускает сервер на `http://127.0.0.1:8080`
- Использует конфигурацию из `.env.local_cloud`

### 3. Создание конфигурационных файлов

Создайте нужные конфигурационные файлы на основе `env.example`:

```bash
# Для локального облака
cp env.example .env.local_cloud

# Для тестирования
cp env.example .env.test

# Для продакшена
cp env.example .env.production
```

### 4. Ручное управление конфигурацией

Вы можете вручную установить переменную `ENV_FILE`:

```bash
# Windows PowerShell
$env:ENV_FILE=".env.local_cloud"
python run_server.py

# Linux/macOS
export ENV_FILE=".env.local_cloud"
python run_server.py
```

## Измененные файлы

### Основные изменения:
- `app/core/config.py` - поддержка переменной `ENV_FILE`
- `run_local_cloud.py` - новый скрипт для локального облака

### Обновленные файлы с поддержкой ENV_FILE:
- `app/core/database.py`
- `run_polling.py`
- `scripts/create_schedule_tables.py`
- `scripts/create_master_schedules_table.py`
- `test_schedule_data.py`
- `scripts/seed_work_schedules.py`
- `scripts/analyze_dialogues.py`
- `scripts/seed_knowledge_base.py`

## Пример конфигурации для локального облака

Создайте файл `.env.local_cloud` со следующими настройками:

```env
# YDB Configuration
YDB_ENDPOINT=grpcs://ydb.serverless.yandexcloud.net:2135
YDB_DATABASE=/your/database/path

# Telegram Bot
TELEGRAM_BOT_TOKEN=your_bot_token

# LLM Provider
LLM_PROVIDER=google

# Logging - используем облачный режим для симуляции
LOG_MODE=cloud

# S3 Configuration для логирования
S3_ACCESS_KEY_ID=your_access_key
S3_SECRET_ACCESS_KEY=your_secret_key
S3_BUCKET_NAME=your_bucket
S3_ENDPOINT_URL=https://storage.yandexcloud.net
```

## Преимущества

1. **Изоляция сред**: Каждая среда имеет свою конфигурацию
2. **Простое переключение**: Один скрипт для локального облака
3. **Безопасность**: Разные токены и ключи для разных сред
4. **Отладка**: Легко тестировать облачные настройки локально
