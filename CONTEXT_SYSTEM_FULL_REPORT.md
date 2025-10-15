# Полный отчет: Система контекста для работы с записями

## Обзор системы

Система контекста в проекте салона красоты предназначена для эффективного управления операциями с записями клиентов (просмотр, редактирование, изменение, удаление, добавление). Основная цель - обеспечить LLM необходимой информацией о записях клиента для корректного выполнения операций без необходимости повторных запросов к базе данных.

## Архитектура системы

### 1. Кратковременная память сессий

**Расположение:** `app/services/dialog_service.py`, строки 76-78

```python
# Кратковременная память о контексте сессий для каждого пользователя
# Формат: {user_id: {"appointments_in_focus": [{"id": int, "details": str}, ...], ...}}
self.session_contexts = {}
```

**Формат данных:**
```python
{
    user_id: {
        "appointments_in_focus": [
            {"id": 42, "details": "16 October в 16:30: Маникюр с покрытием гель-лак к мастеру Елизавета"},
            {"id": 43, "details": "17 October в 14:00: Стрижка к мастеру Мария"}
        ]
    }
}
```

### 2. Определение стадий для скрытого контекста

**Расположение:** `app/services/dialog_service.py`, строки 267-288

Стадии, требующие скрытого контекста:
- `cancellation_request` - отмена записи
- `rescheduling` - перенос записи  
- `appointment_cancellation` - отмена записи (устаревшая стадия)
- `view_booking` - просмотр записей

## Логика работы системы

### Этап 1: Планирование (DialogService.process_user_message)

#### 1.1 Формирование скрытого контекста ДО планирования

**Расположение:** `app/services/dialog_service.py`, строки 133-144

```python
# Формируем скрытый контекст ДО планирования
hidden_context = ""

# Проверяем, есть ли записи в памяти для формирования скрытого контекста
if 'appointments_in_focus' in session_context:
    appointments_data = session_context.get('appointments_in_focus', [])
    if appointments_data:
        hidden_context = "# СКРЫТЫЙ КОНТЕКСТ ЗАПИСЕЙ (ИСПОЛЬЗУЙ ДЛЯ ИЗВЛЕЧЕНИЯ ID):\n" + json.dumps(appointments_data, ensure_ascii=False)
```

#### 1.2 Передача в промпт планирования

**Расположение:** `app/services/dialog_service.py`, строки 146-151

```python
# Формируем промпт для планирования
planning_prompt = self.prompt_builder.build_planning_prompt(
    history=dialog_history,
    user_message=text,
    hidden_context=hidden_context
)
```

#### 1.3 Интеграция в шаблон промпта

**Расположение:** `app/services/prompt_builder_service.py`, строки 53, 268

В шаблоне планирования есть плейсхолдер `{hidden_context}`:
```python
{hidden_context}

# ИСТОРИЯ ДИАЛОГА
{history}
```

### Этап 2: Выполнение инструментов

#### 2.1 Сохранение записей в память после get_my_appointments

**Расположение:** `app/services/dialog_service.py`, строки 245-254

```python
# Сохраняем результат в память, если это get_my_appointments
if tool_name == 'get_my_appointments':
    # Получаем структурированные данные напрямую из AppointmentService
    appointments_data = self.appointment_service.get_my_appointments(user_id)
    session_context['appointments_in_focus'] = appointments_data
    logger.info(f"🔍 Записи сохранены в память: {appointments_data}")
```

#### 2.2 Автоматическое получение записей для стадий отмены/переноса

**Расположение:** `app/services/dialog_service.py`, строки 267-287

```python
# Логика скрытого контекста: получаем записи если их нет в памяти для стадий отмены/переноса
if stage in ['cancellation_request', 'rescheduling']:
    # Если нет записей в памяти, получаем их
    if 'appointments_in_focus' not in session_context:
        appointments_data = self.appointment_service.get_my_appointments(user_id)
        session_context['appointments_in_focus'] = appointments_data
        
    # Обновляем скрытый контекст с актуальными данными
    appointments_data = session_context.get('appointments_in_focus', [])
    if appointments_data:
        hidden_context = "# СКРЫТЫЙ КОНТЕКСТ ЗАПИСЕЙ (ИСПОЛЬЗУЙ ДЛЯ ИЗВЛЕЧЕНИЯ ID):\n" + json.dumps(appointments_data, ensure_ascii=False)
```

### Этап 3: Синтез ответа

#### 3.1 Добавление скрытого контекста для синтеза

**Расположение:** `app/services/dialog_service.py`, строки 325-331

```python
# Добавляем скрытый контекст к результатам инструментов для этапа синтеза
if hidden_context:
    tool_results += "\n" + hidden_context
    tracer.add_event("🔍 Скрытый контекст добавлен к результатам", {
        "stage": stage,
        "context": hidden_context
    })
```

### Этап 4: Очистка памяти

#### 4.1 Логика очистки памяти

**Расположение:** `app/services/dialog_service.py`, строки 289-292

```python
# Логика очистки памяти: очищаем память о записях, если сменили тему
if stage not in ['appointment_cancellation', 'rescheduling', 'view_booking', 'cancellation_request']:
    if 'appointments_in_focus' in session_context:
        del session_context['appointments_in_focus']  # Очищаем, если сменили тему
```

## Операции с записями

### 1. Просмотр записей (view_booking)

**Инструмент:** `get_my_appointments`
**Расположение:** `app/services/tool_service.py`, строки 221-231

```python
def get_my_appointments(self, user_telegram_id: int) -> list:
    """
    Получает все предстоящие записи пользователя в структурированном виде.
    
    Returns:
        Список словарей с записями, где каждый словарь содержит 'id' и 'details'
    """
    return self.appointment_service.get_my_appointments(user_telegram_id=user_telegram_id)
```

**Реализация в AppointmentService:**
**Расположение:** `app/services/appointment_service.py`, строки 156-192

```python
def get_my_appointments(self, user_telegram_id: int) -> list:
    """
    Получает все предстоящие записи пользователя в структурированном виде.
    
    Returns:
        Список словарей с записями: [{"id": int, "details": str}, ...]
    """
    try:
        appointments = self.appointment_repository.get_future_appointments_by_user(user_telegram_id)
        
        if not appointments:
            return []
        
        appointments_data = []
        for appointment in appointments:
            # Форматируем дату и время
            date_str = appointment.start_time.strftime("%d %B")
            time_str = appointment.start_time.strftime("%H:%M")
            
            # Формируем детальное описание
            details = f"{date_str} в {time_str}: {appointment.service.name} к мастеру {appointment.master.name}"
            
            appointments_data.append({
                "id": appointment.id,
                "details": details
            })
        
        return appointments_data
    except Exception as e:
        return []
```

### 2. Отмена записи (cancellation_request)

**Инструмент:** `cancel_appointment_by_id`
**Расположение:** `app/services/tool_service.py`, строки 233-244

```python
def cancel_appointment_by_id(self, appointment_id: int, user_telegram_id: int) -> str:
    """
    Отменяет запись по её ID.
    
    Args:
        appointment_id: ID записи для отмены
        user_telegram_id: ID пользователя в Telegram
    
    Returns:
        Подтверждение отмены или сообщение об ошибке
    """
    return self.appointment_service.cancel_appointment_by_id(appointment_id=appointment_id, user_telegram_id=user_telegram_id)
```

**Реализация в AppointmentService:**
**Расположение:** `app/services/appointment_service.py`, строки 194-227

```python
def cancel_appointment_by_id(self, appointment_id: int, user_telegram_id: int) -> str:
    """
    Отменяет запись по её ID.
    
    Args:
        appointment_id: ID записи для отмены
        user_telegram_id: ID пользователя в Telegram для проверки прав доступа
    
    Returns:
        Подтверждение отмены или сообщение об ошибке
    """
    try:
        # Проверяем права доступа
        appointment = self.appointment_repository.get_by_id(appointment_id)
        if not appointment or appointment.user_telegram_id != user_telegram_id:
            return "Запись не найдена или у вас нет прав для её отмены."
        
        # Получаем информацию о записи
        master_name = appointment.master.name
        service_name = appointment.service.name
        date_str = appointment.start_time.strftime("%d %B")
        time_str = appointment.start_time.strftime("%H:%M")
        
        # Сначала пытаемся удалить событие в Google Calendar (не критично, если не удастся)
        try:
            self.google_calendar_service.delete_event(appointment.google_event_id)
        except Exception as calendar_error:
            # Логируем, но не блокируем удаление в БД
            logger.warning(f"⚠️ Не удалось удалить событие в календаре: {calendar_error}")

        # Удаляем запись из нашей БД напрямую по объекту и проверяем результат
        deleted = self.appointment_repository.delete(appointment)
        if not deleted:
            return "Ошибка при отмене записи. Попробуйте позже."
        
        return f"Ваша запись на {service_name} {date_str} в {time_str} к мастеру {master_name} успешно отменена."
        
    except Exception as e:
        logger.error(f"Ошибка при отмене записи {appointment_id}: {e}")
        return "Произошла ошибка при отмене записи. Попробуйте позже."
```

### 3. Перенос записи (rescheduling)

**Инструмент:** `reschedule_appointment_by_id`
**Расположение:** `app/services/tool_service.py`, строки 246-269

```python
def reschedule_appointment_by_id(self, appointment_id: int, new_date: str, new_time: str, user_telegram_id: int) -> str:
    """
    Переносит запись на новую дату и время по её ID.
    
    Args:
        appointment_id: ID записи для переноса
        new_date: Новая дата в любом поддерживаемом формате
        new_time: Новое время в формате "HH:MM"
        user_telegram_id: ID пользователя в Telegram
    
    Returns:
        Подтверждение переноса или сообщение об ошибке
    """
    # Парсим дату в стандартный формат
    parsed_date = parse_date_string(new_date)
    if parsed_date is None:
        return f"Неверный формат даты: {new_date}. Ожидается формат YYYY-MM-DD."
    
    return self.appointment_service.reschedule_appointment_by_id(
        appointment_id=appointment_id,
        new_date=parsed_date,
        new_time=new_time,
        user_telegram_id=user_telegram_id
    )
```

### 4. Создание записи (booking_confirmation)

**Инструмент:** `create_appointment`
**Расположение:** `app/services/tool_service.py`, строки 170-197

```python
def create_appointment(self, master_name: str, service_name: str, date: str, time: str, client_name: str, user_telegram_id: int) -> str:
    """
    Создает запись в календаре для мастера и услуги.
    
    Args:
        master_name: Имя мастера
        service_name: Название услуги
        date: Дата в любом поддерживаемом формате
        time: Время в формате "HH:MM"
        client_name: Имя клиента
        user_telegram_id: ID пользователя в Telegram
    
    Returns:
        Строка с подтверждением записи или сообщение об ошибке
    """
    # Парсим дату в стандартный формат
    parsed_date = parse_date_string(date)
    if parsed_date is None:
        return f"Неверный формат даты: {date}. Ожидается формат YYYY-MM-DD."
    
    return self.appointment_service.create_appointment(
        master_name=master_name,
        service_name=service_name,
        date=parsed_date,
        time=time,
        client_name=client_name,
        user_telegram_id=user_telegram_id
    )
```

## Интеграция с промптами

### 1. Планирование промпт

**Расположение:** `app/services/prompt_builder_service.py`, строки 28-86

В шаблоне планирования есть специальная секция для скрытого контекста:

```python
{hidden_context}

# ИСТОРИЯ ДИАЛОГА
{history}
```

**Цели по стадиям для работы с записями:**
- `view_booking`: Получи список записей клиента, используя `get_my_appointments`
- `cancellation_request`: Отмени запись, используя `cancel_appointment_by_id`
- `rescheduling`: Перенеси запись, используя `reschedule_appointment_by_id`
- `booking_confirmation`: Проверь наличие всех данных и вызови `create_appointment`

### 2. Синтез промпт

**Расположение:** `app/services/prompt_builder_service.py`, строки 88-121

Скрытый контекст добавляется к результатам инструментов и передается в промпт синтеза для формирования финального ответа.

## Примеры работы системы

### Пример 1: Успешная отмена записи

**Входные данные:**
- Пользователь: "отмените запись"
- Стадия: `cancellation_request`
- Записи в памяти: `[{"id": 42, "details": "16 October в 16:30: Маникюр к мастеру Елизавета"}]`

**Скрытый контекст:**
```
# СКРЫТЫЙ КОНТЕКСТ ЗАПИСЕЙ (ИСПОЛЬЗУЙ ДЛЯ ИЗВЛЕЧЕНИЯ ID):
[{"id": 42, "details": "16 October в 16:30: Маникюр к мастеру Елизавета"}]
```

**Результат LLM:**
```json
{
  "stage": "cancellation_request",
  "tool_calls": [
    {
      "tool_name": "cancel_appointment_by_id",
      "parameters": {
        "user_telegram_id": 261617302,
        "appointment_id": 42
      }
    }
  ]
}
```

### Пример 2: Автоматическое получение записей

**Сценарий:** Пользователь сразу говорит "отмените", без предварительного просмотра записей.

**Логика:**
1. Определяется стадия `cancellation_request`
2. Проверяется память сессии - пустая
3. Автоматически вызывается `get_my_appointments(user_id)`
4. Записи сохраняются в память
5. Формируется скрытый контекст
6. LLM получает ID записей и может правильно вызвать инструмент

### Пример 3: Просмотр записей

**Входные данные:**
- Пользователь: "покажите мои записи"
- Стадия: `view_booking`

**Выполнение:**
1. LLM вызывает `get_my_appointments`
2. Результат сохраняется в память сессии
3. Формируется читаемый ответ для пользователя

## Отладочные логи и трассировка

### Ключевые события для мониторинга:

1. **Определение стадии:**
   ```
   🔍 Определена стадия: cancellation_request
   ```

2. **Сохранение записей в память:**
   ```
   🔍 Записи сохранены в память: [{"id": 42, "details": "..."}]
   ```

3. **Формирование скрытого контекста:**
   ```
   🔍 Скрытый контекст сформирован ДО планирования
   ```

4. **Добавление контекста к результатам:**
   ```
   🔍 Скрытый контекст добавлен к результатам
   ```

5. **Очистка памяти:**
   ```
   🔍 Память очищена (смена темы)
   ```

## Преимущества системы

1. **Эффективность:** Избегает повторных запросов к БД в рамках одной сессии
2. **Контекстность:** LLM имеет доступ к актуальным данным о записях клиента
3. **Автоматизация:** Автоматически получает записи при необходимости
4. **Безопасность:** Проверяет права доступа перед операциями
5. **Надежность:** Обрабатывает ошибки и предоставляет fallback

## Ограничения и рекомендации

1. **Время жизни памяти:** Память очищается при смене темы диалога
2. **Размер контекста:** Ограничен размером окна контекста LLM
3. **Синхронизация:** Память может устареть при изменениях извне
4. **Масштабирование:** При большом количестве пользователей может потребоваться оптимизация

## Заключение

Система контекста для работы с записями представляет собой комплексное решение, которое обеспечивает эффективное взаимодействие между пользователем и AI-ассистентом при выполнении операций с записями. Она сочетает в себе кратковременную память сессий, автоматическое получение данных и интеллектуальную интеграцию с промптами LLM для достижения максимальной эффективности и удобства использования.
