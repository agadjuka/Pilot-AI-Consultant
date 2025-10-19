# 📊 Полный анализ команды "Get Available Slots" в системе салона красоты

## 🎯 Обзор системы

**Система:** AI-консультант салона красоты с поддержкой записи на услуги  
**Команда:** `get_available_slots` - получение свободных временных слотов для услуги  
**Архитектура:** Трехэтапная система обработки диалогов (Классификация → Мышление → Синтез)  
**База данных:** Локальная SQLite база данных (НЕ Google Calendar)

---

## 🔄 Полный алгоритм обработки команды

### 1. 📨 Получение команды от пользователя

**Точка входа:** `app/api/telegram.py:14-50`
```python
async def process_telegram_update(update: Update):
    # Получение сообщения от Telegram
    chat_id = update.message.chat.id
    user_id = update.message.from_user.id
    text = update.message.text
    
    # Создание DialogService и обработка сообщения
    dialog_service = DialogService()
    bot_response = await dialog_service.process_user_message(user_id, text)
```

**Поток данных:**
1. Telegram → Webhook (`/telegram/{bot_token}`)
2. Парсинг JSON в объект `Update`
3. Передача в `DialogService.process_user_message()`

---

### 2. 🧠 Трехэтапная обработка в DialogService

**Файл:** `app/services/dialog_service.py:468-981`

#### Этап 1: Классификация (строки 527-558)
```python
# Определение стадии диалога
classification_prompt = self.prompt_builder.build_classification_prompt(
    history=dialog_history,
    user_message=text
)
stage_str = await self.llm_service.generate_response(classification_history)
stage = self.parse_stage(stage_str)  # Например: "availability_check"
```

**Результат:** Определение стадии диалога (например, `availability_check`)

#### Этап 2: Мышление (строки 620-778)
```python
# Формирование промпта для мышления
thinking_prompt = self.prompt_builder.build_thinking_prompt(
    stage_name=stage,
    history=dialog_history,
    user_message=text,
    client_name=client['first_name'],
    client_phone_saved=bool(client['phone_number'])
)

# Вызов LLM с доступными инструментами
filtered_tools = self._get_filtered_tools(available_tools)
thinking_response = await self.llm_service.generate_response(thinking_history, filtered_tools)

# Парсинг ответа и извлечение вызовов инструментов
cleaned_text, tool_calls = self.parse_string_format_response(thinking_response)
```

**Результат:** LLM решает вызвать `get_available_slots(service_name="маникюр", date="2025-10-15")`

#### Этап 3: Синтез (строки 780-981)
```python
# Формирование финального ответа
synthesis_prompt = self.prompt_builder.build_synthesis_prompt(
    stage_name=stage,
    history=dialog_history,
    user_message=text,
    tool_results=tool_results,
    client_name=client['first_name']
)

# Генерация финального ответа пользователю
synthesis_response = await self.llm_service.generate_response(synthesis_history, filtered_tools)
```

---

### 3. ⚙️ Выполнение инструмента через ToolOrchestratorService

**Файл:** `app/services/tool_orchestrator_service.py:793-797`

```python
elif function_name == "get_available_slots":
    service_name = function_args.get("service_name", "")
    date = function_args.get("date", "")
    result = method(service_name, date, tracer)
    return result
```

**Поток данных:**
1. `ToolOrchestratorService.execute_single_tool()` → 
2. `ToolService.get_available_slots()` →
3. `DBCalendarService.get_free_slots()`

---

### 4. 🔍 Основная логика в ToolService

**Файл:** `app/services/tool_service.py:118-211`

#### Шаг 1: Парсинг даты
```python
parsed_date = parse_date_robust(date)  # app/utils/robust_date_parser.py
if parsed_date is None:
    return f"Неверный формат даты: {date}. Ожидается формат YYYY-MM-DD."
```

#### Шаг 2: Поиск услуги
```python
# Получение всех услуг из БД
all_services = self.service_repository.get_all()

# Нечеткий поиск услуги по названию
service = self._find_service_by_fuzzy_match(service_name, all_services)

if not service:
    # Поиск похожих услуг
    similar_services = self._find_similar_services(service_name, all_services)
    return f"Услуга '{service_name}' не найдена. Возможно: {', '.join(similar_services)}?"
```

#### Шаг 3: Поиск мастеров
```python
# Получение мастеров, выполняющих услугу
masters = self.master_repository.get_masters_for_service(service['id'])
if not masters:
    return f"Нет мастеров, выполняющих услугу '{decoded_service_name}'."

# Извлечение ID мастеров
master_ids = [master['id'] for master in masters]
master_names = [self._decode_string_field(master['name']) for master in masters]
```

#### Шаг 4: Вызов календаря
```python
# Получение длительности услуги
duration_minutes = service['duration_minutes']

# Вызов DBCalendarService для поиска свободных слотов
free_intervals = self.db_calendar_service.get_free_slots(
    parsed_date,
    duration_minutes,
    master_ids=master_ids,
    tracer=tracer
)
```

#### Шаг 5: Форматирование результата
```python
if free_intervals:
    interval_strings = [f"{interval['start']}-{interval['end']}" for interval in free_intervals]
    return ", ".join(interval_strings)  # Например: "10:15-13:45, 15:00-17:30"
```

#### Шаг 6: Поиск альтернативных дат (если нет слотов)
```python
# Если на запрошенную дату мест нет, ищем ближайшие доступные слоты
original_date = datetime.strptime(parsed_date, "%Y-%m-%d")

for i in range(1, 8):  # Проверяем следующие 7 дней
    next_date = original_date + timedelta(days=i)
    next_date_str = next_date.strftime("%Y-%m-%d")
    
    next_free_intervals = self.db_calendar_service.get_free_slots(
        next_date_str,
        duration_minutes,
        master_ids=master_ids
    )
    
    if next_free_intervals:
        first_interval = next_free_intervals[0]
        return f"На {parsed_date} мест нет. Ближайшее окно: {next_date_str}, {first_interval['start']}-{first_interval['end']}"
```

---

### 5. 📅 Алгоритм расчета слотов в DBCalendarService

**Файл:** `app/services/db_calendar_service.py:149-441`

#### Основной метод: `get_free_slots()`
```python
def get_free_slots(self, date: str, duration_minutes: int, master_ids: List[int], tracer=None):
    # Парсинг даты
    target_date = datetime.strptime(date, "%Y-%m-%d").date()
    
    # Шаг 1: Получение рабочих интервалов мастеров
    work_intervals = self._get_work_intervals_for_masters(target_date, master_ids)
    
    # Шаг 2: Получение записей на дату
    appointments = self._get_appointments_for_masters_on_date(target_date, master_ids)
    
    # Шаг 3: Расчет свободных интервалов через таймлайн
    free_intervals = self._calculate_free_intervals_timeline(work_intervals, appointments)
    
    # Шаг 4: Фильтрация по длительности
    filtered_intervals = self._filter_intervals_by_duration(free_intervals, duration_minutes)
    
    return filtered_intervals
```

#### Шаг 1: Получение рабочих интервалов
```python
def _get_work_intervals_for_masters(self, target_date: date, master_ids: List[int]):
    work_intervals = {}
    
    for master_id in master_ids:
        work_time = self._get_master_work_time(target_date, master_id)
        if work_time:
            start_time, end_time = work_time
            work_intervals[master_id] = (start_time, end_time)
    
    return work_intervals
```

**Рабочие часы:** Фиксированные 9:00-18:00, воскресенье - выходной
```python
def _get_master_work_time(self, target_date: date, master_id: int):
    day_of_week = target_date.weekday()
    if day_of_week == 6:  # Воскресенье
        return None
    
    start_time = time(9, 0)  # 9:00
    end_time = time(18, 0)   # 18:00
    return (start_time, end_time)
```

#### Шаг 2: Получение записей из БД
```python
def _get_appointments_for_masters_on_date(self, target_date: date, master_ids: List[int]):
    master_ids_str = ','.join(map(str, master_ids))
    
    query = f"""
        SELECT * FROM appointments 
        WHERE master_id IN ({master_ids_str})
        AND CAST(start_time AS Date) = CAST('{target_date}' AS Date)
        ORDER BY start_time
    """
    
    rows = execute_query(query)
    appointments = []
    for row in rows:
        appointment = self.appointment_repository._row_to_dict(row)
        appointments.append(appointment)
    
    return appointments
```

#### Шаг 3: Алгоритм "Таймлайн занятости"
```python
def _calculate_free_intervals_timeline(self, work_intervals: Dict, appointments: List):
    timeline = []
    
    # Добавляем события начала и окончания работы мастеров
    for master_id, (start_time, end_time) in work_intervals.items():
        timeline.append((start_time, 1, 'work_start', master_id))  # +1 свободен
        timeline.append((end_time, -1, 'work_end', master_id))     # -1 ушел с работы
    
    # Добавляем события записей
    for appointment in appointments:
        start_time = appointment['start_time'].time()
        end_time = appointment['end_time'].time()
        
        timeline.append((start_time, -1, 'appointment_start', appointment['master_id']))  # -1 занят
        timeline.append((end_time, 1, 'appointment_end', appointment['master_id']))       # +1 освободился
    
    # Сортируем таймлайн по времени
    timeline.sort(key=lambda x: x[0])
    
    # Проходим по таймлайну и находим свободные интервалы
    free_intervals = []
    available_masters_count = 0
    current_start = None
    
    for timestamp, delta, event_type, master_id in timeline:
        available_masters_count += delta
        
        if available_masters_count > 0 and current_start is None:
            # Начинается свободный интервал
            current_start = timestamp
        elif available_masters_count == 0 and current_start is not None:
            # Заканчивается свободный интервал
            free_intervals.append({
                'start': current_start.strftime('%H:%M'),
                'end': timestamp.strftime('%H:%M')
            })
            current_start = None
    
    return free_intervals
```

#### Шаг 4: Фильтрация по длительности
```python
def _filter_intervals_by_duration(self, intervals: List, duration_minutes: int):
    filtered_intervals = []
    
    for interval in intervals:
        start_time = datetime.strptime(interval['start'], '%H:%M').time()
        end_time = datetime.strptime(interval['end'], '%H:%M').time()
        
        # Вычисляем длительность интервала
        start_datetime = datetime.combine(date.today(), start_time)
        end_datetime = datetime.combine(date.today(), end_time)
        duration = (end_datetime - start_datetime).total_seconds() / 60
        
        if duration >= duration_minutes:
            filtered_intervals.append(interval)
    
    return filtered_intervals
```

---

## 🗄️ Структура базы данных

### Таблица `services`
```sql
CREATE TABLE services (
    id INTEGER PRIMARY KEY,
    name VARCHAR NOT NULL,
    description TEXT,
    price FLOAT NOT NULL,
    duration_minutes INTEGER NOT NULL
);
```

### Таблица `masters`
```sql
CREATE TABLE masters (
    id INTEGER PRIMARY KEY,
    name VARCHAR NOT NULL,
    specialization VARCHAR
);
```

### Таблица `master_services` (связь многие-ко-многим)
```sql
CREATE TABLE master_services (
    master_id INTEGER REFERENCES masters(id),
    service_id INTEGER REFERENCES services(id),
    PRIMARY KEY (master_id, service_id)
);
```

### Таблица `appointments`
```sql
CREATE TABLE appointments (
    id INTEGER PRIMARY KEY,
    user_telegram_id BIGINT NOT NULL,
    master_id INTEGER REFERENCES masters(id),
    service_id INTEGER REFERENCES services(id),
    start_time DATETIME NOT NULL,
    end_time DATETIME NOT NULL
);
```

---

## 🔧 Репозитории и их роль

### ServiceRepository (`app/repositories/service_repository.py`)
- `get_all()` - получение всех услуг
- `get_by_name()` - поиск услуги по точному названию
- `search_by_name()` - поиск услуг по частичному совпадению

### MasterRepository (`app/repositories/master_repository.py`)
- `get_masters_for_service(service_id)` - получение мастеров для услуги
- `get_all()` - получение всех мастеров

### AppointmentRepository (`app/repositories/appointment_repository.py`)
- `_row_to_dict()` - конвертация строки БД в словарь
- Работа с записями через SQL запросы

---

## 📝 Форматы данных

### Входные параметры
```python
get_available_slots(
    service_name: str,  # Например: "маникюр", "стрижка"
    date: str          # Например: "2025-10-15", "завтра", "15.10.2025"
)
```

### Выходной формат
```python
# Успешный результат
"10:15-13:45, 15:00-17:30"

# Нет слотов на дату
"На 2025-10-15 мест нет. Ближайшее окно: 2025-10-16, 10:00-12:00"

# Ошибка поиска услуги
"Услуга 'маникюр' не найдена. Возможно: Маникюр гель-лак, Маникюр классический?"

# Нет мастеров
"К сожалению, на данный момент нет мастеров, выполняющих услугу 'Маникюр'."
```

---

## 🎯 Паттерны диалогов

**Файл:** `dialogue_patterns.json`

### Стадия `availability_check`
```json
{
    "stage": "availability_check",
    "description": "Проверка доступных слотов",
    "thinking_rules": "Вызови инструмент get_available_slots с этими данными",
    "thinking_tools": "get_available_slots(service_name: str, date: str)",
    "available_tools": ["get_available_slots"]
}
```

---

## 🔍 Трассировка и логирование

### DialogueTracer (`app/services/dialogue_tracer_service.py`)
```python
tracer.add_event("🔍 Начало поиска слотов", f"Дата: {date}, Длительность: {duration_minutes} мин")
tracer.add_event("💅 Услуга найдена", f"Название: {service_name}, Длительность: {duration_minutes} мин")
tracer.add_event("👥 Мастера найдены", f"Количество: {len(master_names)}, Имена: {', '.join(master_names)}")
tracer.add_event("🕐 Свободные слоты найдены", f"Количество: {len(free_intervals)}, Интервалы: {', '.join(interval_strings)}")
```

---

## ⚡ Производительность и оптимизации

### 1. Кэширование контекста
- Сессионный контекст для каждого пользователя
- Кэширование данных о записях клиента

### 2. Эффективные SQL запросы
- Индексы на `user_telegram_id`, `start_time`
- Фильтрация по дате на уровне БД

### 3. Алгоритм таймлайна
- O(n log n) сложность сортировки событий
- Линейный проход по отсортированному таймлайну

---

## 🚨 Обработка ошибок

### 1. Неверный формат даты
```python
if parsed_date is None:
    return f"Неверный формат даты: {date}. Ожидается формат YYYY-MM-DD."
```

### 2. Услуга не найдена
```python
if not service:
    similar_services = self._find_similar_services(service_name, all_services)
    if similar_services:
        return f"Услуга '{service_name}' не найдена. Возможно: {', '.join(similar_services)}?"
```

### 3. Нет мастеров
```python
if not masters:
    return f"К сожалению, на данный момент нет мастеров, выполняющих услугу '{decoded_service_name}'."
```

### 4. Ошибки БД
```python
except Exception as e:
    logger.error(f"❌ [DB CALENDAR] Ошибка поиска свободных слотов: {str(e)}")
    raise Exception(f"Ошибка при поиске свободных слотов: {str(e)}")
```

---

## 📊 Статистика и метрики

### Логирование ключевых событий
- Время выполнения каждого этапа
- Количество найденных слотов
- Количество мастеров для услуги
- Ошибки парсинга дат

### Трассировка диалогов
- Полная история выполнения команды
- Параметры вызовов инструментов
- Результаты каждого шага

---

## 🔄 Альтернативные сценарии

### 1. Поиск на следующие дни
Если на запрошенную дату нет слотов, система автоматически ищет в течение 7 дней вперед.

### 2. Нечеткий поиск услуг
Система использует алгоритм нечеткого поиска для нахождения услуг по частичному совпадению названий.

### 3. Fallback ответы
При ошибках система генерирует дружелюбные сообщения вместо технических ошибок.

---

## 🎯 Заключение

Команда `get_available_slots` представляет собой сложную многоэтапную систему, которая:

1. **Принимает** запрос пользователя через Telegram
2. **Классифицирует** стадию диалога через LLM
3. **Анализирует** запрос и определяет необходимые инструменты
4. **Выполняет** поиск услуги, мастеров и свободных слотов
5. **Рассчитывает** доступность через алгоритм таймлайна
6. **Форматирует** результат для пользователя
7. **Предлагает** альтернативы при отсутствии слотов

Система обеспечивает высокую надежность, детальную трассировку и дружелюбный пользовательский интерфейс.
