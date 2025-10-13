# 🔌 Подключение к Gemini 2.5 Flash - Краткая инструкция

## 📋 Основные компоненты

### 1. Переменные окружения (env.local)
```
BOT_TOKEN=ваш_токен
PROJECT_ID=ваш_проект_id
GOOGLE_APPLICATION_CREDENTIALS=путь/к/credentials.json
GOOGLE_CLOUD_LOCATION=asia-southeast1
FIRESTORE_DATABASE=docbot
```

### 2. Файл учетных данных
- **Файл**: `bot-doc-473208-706e6adceee1.json`
- **Формат**: Service Account JSON от Google Cloud
- **Scopes**: `https://www.googleapis.com/auth/generative-language`

## 🔧 Процесс инициализации

### Шаг 1: Загрузка env (main_local.py:27-29)
```python
env_path = os.path.join(os.path.dirname(__file__), "env.local")
load_dotenv(env_path)
```

### Шаг 2: Настройка credentials (main_local.py:62-75)
```python
credentials_path = "bot-doc-473208-706e6adceee1.json"
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
os.environ["FIRESTORE_DATABASE"] = "docbot"
```

### Шаг 3: Инициализация Gemini (ai_service.py:42-115)
**3 варианта получения credentials:**

1. **GOOGLE_APPLICATION_CREDENTIALS_JSON** (для Cloud Run):
   - JSON напрямую в переменной окружения
   - `service_account.Credentials.from_service_account_info()`

2. **GOOGLE_APPLICATION_CREDENTIALS** (локально):
   - Путь к JSON файлу или сам JSON
   - `service_account.Credentials.from_service_account_file()`

3. **Application Default Credentials** (ADC):
   - Автоматически для Cloud Run
   - `google.auth.default()`

### Шаг 4: Конфигурация модели (ai_service.py:104-109)
```python
genai.configure(credentials=credentials)
model_name = config.get_model_name(model_type)  # "gemini-2.5-flash"
self._model = genai.GenerativeModel(model_name)
```

## 🌍 Локации моделей (settings.py:85-92)

| Модель | Локация | Переменная |
|--------|---------|-----------|
| **Flash** | `asia-southeast1` | `LOCATION` |
| **Pro** | `global` | `LOCATION_GLOBAL` |

## 🏭 AIServiceFactory (ai_service.py:446-479)

**Назначение**: Управление несколькими моделями одновременно

```python
ai_factory = AIServiceFactory(config, prompt_manager)
ai_service = ai_factory.get_service("flash")  # или "pro"
```

**Кэширование**: Экземпляры моделей хранятся в `_services = {}`

## 🎯 Основные методы AIService

1. **get_ai_response()** - базовый ответ AI
2. **analyze_document_structure()** - анализ HTML документа  
3. **generate_document_filling_plan()** - план заполнения документа

## 📊 Дополнительные сервисы

- **DebugService** - логирование запросов/ответов Gemini
- **TimingService** - измерение времени запросов
- **Кэш** - `_ai_service_cache` для переиспользования экземпляров

## ✅ Порядок запуска (main_local.py:180-213)

```python
1. load_dotenv(env_path)                      # Загрузка переменных
2. setup_environment()                        # Настройка credentials
3. config = BotConfig()                       # Конфигурация
4. ai_factory = AIServiceFactory(config, pm)  # Фабрика сервисов
5. ai_service = ai_factory.get_default_service() # Получение сервиса (Pro)
6. analysis_service = ReceiptAnalysisServiceCompat() # Обертка
```

## 🔍 Debug и мониторинг

- **Логи запросов**: `debug_gemini_logs/`
- **Timing stats**: `/timing_stats` команда
- **Модель по умолчанию**: `DEFAULT_MODEL = "pro"` (settings.py:36)

## 🚨 Важные моменты

1. ✅ Credentials загружаются **до импорта** google.cloud модулей
2. ✅ Firestore использует ту же credentials
3. ✅ Flash модель требует `asia-southeast1`
4. ✅ Pro модель работает в `global` локации
5. ✅ Все запросы логируются для отладки

