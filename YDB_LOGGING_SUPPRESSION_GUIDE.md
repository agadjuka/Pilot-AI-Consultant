# 🔇 Руководство по подавлению логов YDB SDK

## Проблема

В консоль постоянно идут сообщения от YDB SDK о токенах:

```
ℹ️ 12:49:54 | INFO | ydb.credentials.MetadataUrlCredentials | Cached token reached refrresh_in deadline, current time 1760935794.0680192, deadline 0
ℹ️ 12:49:59 | INFO | ydb.credentials.MetadataUrlCredentials | Cached token reached refrresh_in deadline, current time 1760935799.3216703, deadline 0
```

Эти сообщения засоряют логи и мешают отладке приложения.

## Решение

Система логирования теперь автоматически подавляет эти сообщения YDB SDK.

### Автоматическое подавление

По умолчанию система логирования настроена на подавление сообщений YDB:

```python
# В app/core/logging_config.py
def setup_logging(level: str = "INFO", enable_colors: bool = True, suppress_ydb_tokens: bool = True):
    # ...
    _configure_module_levels(suppress_ydb_tokens)

def _configure_module_levels(suppress_ydb_tokens: bool = True):
    if suppress_ydb_tokens:
        # Подавляем сообщения YDB SDK о токенах
        logging.getLogger('ydb.credentials.MetadataUrlCredentials').setLevel(logging.ERROR)
        logging.getLogger('ydb.credentials.ServiceAccountCredentials').setLevel(logging.ERROR)
        logging.getLogger('ydb.credentials').setLevel(logging.ERROR)
        logging.getLogger('ydb').setLevel(logging.WARNING)
```

### Что подавляется

- ✅ `ydb.credentials.MetadataUrlCredentials` - сообщения о токенах из метаданных
- ✅ `ydb.credentials.ServiceAccountCredentials` - сообщения о токенах из файла ключа
- ✅ `ydb.credentials` - все сообщения модуля credentials
- ✅ `ydb` - общие сообщения YDB SDK (уровень WARNING)

### Что остается

- ✅ Все сообщения вашего приложения
- ✅ Ошибки YDB SDK (уровень ERROR и выше)
- ✅ Предупреждения YDB SDK (уровень WARNING и выше)

## Настройка

### Отключение подавления (если нужно)

Если вам нужно видеть все сообщения YDB для отладки:

```python
from app.core.logging_config import setup_logging

# Отключаем подавление
setup_logging(suppress_ydb_tokens=False)
```

### Включение подавления (по умолчанию)

```python
from app.core.logging_config import setup_logging

# Включаем подавление (по умолчанию)
setup_logging(suppress_ydb_tokens=True)
```

### Настройка в файлах запуска

**run_polling.py:**
```python
from app.core.logging_config import setup_logging
setup_logging()  # По умолчанию suppress_ydb_tokens=True
```

**app/main.py:**
```python
# Логирование настраивается автоматически при импорте модулей
```

## Тестирование

### Запуск тестового скрипта:

```bash
python test_ydb_logging.py
```

### Что тестируется:

1. **Без подавления** - сообщения YDB видны
2. **С подавлением** - сообщения YDB скрыты
3. **Сообщения приложения** - всегда видны

### Пример вывода:

```
🧪 ТЕСТ: Тестирование подавления логов YDB SDK
============================================================

📋 ТЕСТ 1: Без подавления логов YDB
----------------------------------------
ℹ️ 12:49:54 | INFO | ydb.credentials.MetadataUrlCredentials | Cached token reached refresh_in deadline...

📋 ТЕСТ 2: С подавлением логов YDB
----------------------------------------
ℹ️ 12:49:54 | INFO | app.test | Это сообщение от нашего приложения должно появиться

✅ ТЕСТ: Завершен
```

## Уровни логирования YDB

### До настройки:
- `ydb.credentials.MetadataUrlCredentials` → INFO
- `ydb.credentials.ServiceAccountCredentials` → INFO  
- `ydb.credentials` → INFO
- `ydb` → INFO

### После настройки (с подавлением):
- `ydb.credentials.MetadataUrlCredentials` → ERROR
- `ydb.credentials.ServiceAccountCredentials` → ERROR
- `ydb.credentials` → ERROR
- `ydb` → WARNING

## Дополнительные настройки

### Подавление других библиотек

Система также подавляет сообщения от других библиотек:

```python
def _configure_module_levels(suppress_ydb_tokens: bool = True):
    # Уменьшаем уровень логирования для внешних библиотек
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('google').setLevel(logging.WARNING)
```

### Настройка уровней для ваших модулей

```python
def _configure_module_levels(suppress_ydb_tokens: bool = True):
    # Настраиваем уровень для наших модулей
    logging.getLogger('app.services.dialog_service').setLevel(logging.DEBUG)
    logging.getLogger('app.services.tool_service').setLevel(logging.DEBUG)
    logging.getLogger('app.services.classification_service').setLevel(logging.DEBUG)
```

## Отладка

### Если сообщения YDB все еще появляются:

1. **Проверьте порядок инициализации:**
   ```python
   # Логирование должно настраиваться ПЕРВЫМ
   from app.core.logging_config import setup_logging
   setup_logging()
   
   # Затем импортируйте остальные модули
   import ydb
   ```

2. **Проверьте уровень логирования:**
   ```python
   # Установите DEBUG для проверки
   setup_logging(level="DEBUG", suppress_ydb_tokens=True)
   ```

3. **Проверьте конкретный логгер:**
   ```python
   import logging
   ydb_logger = logging.getLogger('ydb.credentials.MetadataUrlCredentials')
   print(f"Уровень логгера: {ydb_logger.level}")
   print(f"Эффективный уровень: {ydb_logger.getEffectiveLevel()}")
   ```

### Если нужно временно включить логи YDB:

```python
import logging

# Временно включаем логи YDB
logging.getLogger('ydb.credentials.MetadataUrlCredentials').setLevel(logging.INFO)
logging.getLogger('ydb.credentials.ServiceAccountCredentials').setLevel(logging.INFO)
logging.getLogger('ydb.credentials').setLevel(logging.INFO)
logging.getLogger('ydb').setLevel(logging.INFO)
```

## Рекомендации

1. **Оставляйте подавление включенным** в продакшене
2. **Отключайте подавление** только для отладки проблем с YDB
3. **Используйте DEBUG уровень** для детальной отладки
4. **Мониторьте ERROR логи** YDB для критических проблем

## Совместимость

- ✅ Работает с существующим кодом
- ✅ Не влияет на функциональность YDB
- ✅ Не влияет на логи вашего приложения
- ✅ Обратно совместимо
