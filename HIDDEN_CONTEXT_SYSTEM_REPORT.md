# Отчет: Система сохранения скрытых данных в DialogService

## Обзор системы

Система скрытых данных в `DialogService` предназначена для передачи ID записей в промпт планирования LLM, чтобы модель могла правильно вызывать инструменты отмены и переноса записей.

## Архитектура системы

### 1. Кратковременная память сессий

```python
# В DialogService.__init__()
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

```python
def _determine_stage(self, user_message: str, tool_calls: List[Dict]) -> str:
    # Отмена записи
    if any(word in message_lower for word in ['отменить', 'отмена', 'отменить запись', 'отменитте', 'отмените']):
        return 'appointment_cancellation'
```

**Стадии, требующие скрытого контекста:**
- `appointment_cancellation` - отмена записи
- `rescheduling` - перенос записи  
- `cancellation_request` - запрос на отмену (определяется LLM)

## Логика работы системы

### Этап 1: Планирование

#### 1.1 Определение стадии и получение записей

```python
# В process_user_message()
current_stage = self._determine_stage(text, [])
logger.info(f"🔍 Определена стадия: {current_stage}")
logger.info(f"🔍 Память сессии: {session_context}")

if current_stage in ['appointment_cancellation', 'rescheduling', 'cancellation_request']:
    # Если нет записей в памяти, получаем их
    if 'appointments_in_focus' not in session_context:
        appointments_data = self.appointment_service.get_my_appointments(user_id)
        session_context['appointments_in_focus'] = appointments_data
        logger.info(f"🔍 Записи получены и сохранены в память: {appointments_data}")
        tracer.add_event("🔍 Записи получены и сохранены в память", {
            "appointments_count": len(appointments_data),
            "appointments": appointments_data
        })
```

#### 1.2 Формирование скрытого контекста

```python
appointments_data = session_context.get('appointments_in_focus', [])
if appointments_data:
    hidden_context = "# СКРЫТЫЙ КОНТЕКСТ ЗАПИСЕЙ (ИСПОЛЬЗУЙ ДЛЯ ИЗВЛЕЧЕНИЯ ID):\n" + json.dumps(appointments_data, ensure_ascii=False)
    tracer.add_event("🔍 Скрытый контекст для планирования", {
        "stage": current_stage,
        "appointments_count": len(appointments_data),
        "context": hidden_context
    })
```

#### 1.3 Передача в промпт планирования

```python
planning_prompt = self.prompt_builder.build_planning_prompt(
    history=dialog_history,
    user_message=text,
    hidden_context=hidden_context
)
```

### Этап 2: Выполнение инструментов

#### 2.1 Сохранение записей в память после get_my_appointments

```python
# Сохраняем результат в память, если это get_my_appointments
if tool_name == 'get_my_appointments':
    # Получаем структурированные данные напрямую из AppointmentService
    appointments_data = self.appointment_service.get_my_appointments(user_id)
    session_context['appointments_in_focus'] = appointments_data
    logger.info(f"🔍 Записи сохранены в память: {appointments_data}")
    tracer.add_event("🔍 Записи сохранены в память", {
        "appointments_count": len(appointments_data),
        "appointments": appointments_data
    })
```

### Этап 3: Синтез ответа

#### 3.1 Добавление скрытого контекста для синтеза

```python
# Проверяем, есть ли в "памяти" записи и релевантна ли стадия
if stage in ['appointment_cancellation', 'rescheduling', 'cancellation_request'] and 'appointments_in_focus' in session_context:
    appointments_context = session_context['appointments_in_focus']
    # Формируем строку контекста для LLM
    context_str = "КОНТЕКСТ ЗАПИСЕЙ (ДЛЯ ТЕБЯ, НЕ ДЛЯ КЛИЕНТА): " + json.dumps(appointments_context, ensure_ascii=False)
    
    # Добавляем этот контекст к результатам инструментов
    tool_results += "\n" + context_str
    
    tracer.add_event("🔍 Скрытый контекст добавлен", {
        "stage": stage,
        "appointments_count": len(appointments_context),
        "context": context_str
    })
```

### Этап 4: Очистка памяти

#### 4.1 Логика очистки памяти

```python
# Логика очистки памяти: очищаем память о записях, если сменили тему
if stage not in ['appointment_cancellation', 'rescheduling', 'view_booking', 'cancellation_request']:
    if 'appointments_in_focus' in session_context:
        del session_context['appointments_in_focus']  # Очищаем, если сменили тему
```

## Структура данных AppointmentService

### get_my_appointments() возвращает:

```python
def get_my_appointments(self, user_telegram_id: int) -> list:
    """
    Получает все предстоящие записи пользователя в структурированном виде.
    
    Returns:
        Список словарей с записями, где каждый словарь содержит 'id' и 'details'
    """
    result = []
    for appointment in appointments:
        date_str = appointment.start_time.strftime("%d %B")
        time_str = appointment.start_time.strftime("%H:%M")
        master_name = appointment.master.name
        service_name = appointment.service.name
        
        details = f"{date_str} в {time_str}: {service_name} к мастеру {master_name}"
        
        result.append({
            "id": appointment.id,
            "details": details
        })
    
    return result
```

## Шаблон промпта планирования

### PromptBuilderService.planning_template

```python
self.planning_template = """
# ЗАДАЧА
Ты — умный планировщик. Твоя задача — проанализировать НОВОЕ СООБЩЕНИЕ КЛИЕНТА в контексте ИСТОРИИ ДИАЛОГА.

# ИНСТРУМЕНТЫ (Что ты можешь сделать)
{tools_summary}

{hidden_context}

# ИСТОРИЯ ДИАЛОГА
{history}

# НОВОЕ СООБЩЕНИЕ КЛИЕНТА
{user_message}
"""
```

**Плейсхолдер `{hidden_context}`** размещается между инструментами и историей диалога.

## Примеры работы системы

### Пример 1: Успешная отмена записи

**Входные данные:**
- Пользователь: "отмените запись"
- Стадия: `appointment_cancellation`
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
1. Определяется стадия `appointment_cancellation`
2. Проверяется память сессии - пустая
3. Автоматически вызывается `get_my_appointments(user_id)`
4. Записи сохраняются в память
5. Формируется скрытый контекст
6. LLM получает ID записей и может правильно вызвать инструмент

## Отладочные логи

### Ключевые события для мониторинга:

1. **Определение стадии:**
   ```
   🔍 Определена стадия: appointment_cancellation
   ```

2. **Состояние памяти:**
   ```
   🔍 Память сессии: {'appointments_in_focus': [{'id': 42, 'details': '...'}]}
   ```

3. **Получение записей:**
   ```
   🔍 Записи получены и сохранены в память: [{'id': 42, 'details': '...'}]
   ```

4. **Формирование скрытого контекста:**
   ```
   🔍 Скрытый контекст для планирования: {"stage": "appointment_cancellation", "appointments_count": 1, "context": "# СКРЫТЫЙ КОНТЕКСТ..."}
   ```

## Проблемы и решения

### Проблема 1: Стадия определяется как fallback
**Причина:** Неполный список ключевых слов для отмены
**Решение:** Добавлены варианты "отменитте", "отмените"

### Проблема 2: Записи не сохраняются в память
**Причина:** Логика срабатывает только при вызове get_my_appointments
**Решение:** Автоматическое получение записей при определении стадии отмены

### Проблема 3: LLM не видит ID записей
**Причина:** Скрытый контекст не передается в промпт планирования
**Решение:** Добавлен плейсхолдер `{hidden_context}` в шаблон промпта

## Файлы системы

### Основные файлы:
- `app/services/dialog_service.py` - основная логика
- `app/services/prompt_builder_service.py` - формирование промптов
- `app/services/appointment_service.py` - получение записей
- `app/services/tool_service.py` - выполнение инструментов

### Ключевые методы:
- `DialogService.process_user_message()` - основной метод обработки
- `DialogService._determine_stage()` - определение стадии
- `AppointmentService.get_my_appointments()` - получение записей
- `PromptBuilderService.build_planning_prompt()` - формирование промпта

## Заключение

Система скрытых данных обеспечивает передачу ID записей в промпт планирования LLM, что позволяет модели правильно вызывать инструменты отмены и переноса записей. Система работает автоматически и не требует вмешательства пользователя.

**Ключевые особенности:**
- Автоматическое получение записей при необходимости
- Кратковременная память для каждого пользователя
- Очистка памяти при смене темы диалога
- Подробное логирование для отладки
- Поддержка множественных стадий отмены/переноса
