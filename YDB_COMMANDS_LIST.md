# 📋 ПОЛНЫЙ СПИСОК ОБРАЩЕНИЙ К YDB

## 🔧 **Основные функции работы с YDB** (`app/core/database.py`)

### **Подключение и управление сессиями:**
1. `get_driver()` - Создание/получение драйвера YDB
2. `get_session_pool()` - Создание/получение пула сессий
3. `get_db_session()` - Контекстный менеджер для сессий
4. `init_database()` - Инициализация БД и проверка таблиц
5. `close_database()` - Закрытие соединения

### **Основные операции с данными:**
6. `execute_query(query, params)` - Выполнение SELECT запросов
7. `execute_transaction(operations)` - Выполнение транзакций
8. `upsert_record(table, data)` - Вставка/обновление записей
9. `delete_record(table, where_clause)` - Удаление записей

### **Специализированные функции:**
10. `get_all_services()` - Получение всех услуг
11. `get_all_masters()` - Получение всех мастеров
12. `get_master_services(master_id)` - Услуги конкретного мастера
13. `get_client_by_telegram_id(telegram_id)` - Клиент по Telegram ID
14. `add_client(telegram_id, first_name, phone_number)` - Добавление клиента
15. `add_dialog_message(user_id, role, message_text)` - Добавление сообщения в диалог

## 🗂️ **Репозитории** (наследуются от `BaseRepository`)

### **AppointmentRepository** (`app/repositories/appointment_repository.py`):
16. `get_future_appointments_by_user(user_telegram_id)` - Предстоящие записи пользователя
17. `get_next_appointment_by_user(user_telegram_id)` - Ближайшая запись пользователя
18. `check_duplicate_appointment(user_telegram_id, master_id, service_id, start_time)` - Проверка дубликатов
19. `get_appointments_by_master(master_id, date)` - Записи мастера на дату
20. `get_appointments_by_date_range(start_date, end_date)` - Записи в диапазоне дат
21. `delete_by_id(appointment_id)` - Удаление записи по ID
22. `update(appointment_id, data)` - Обновление записи

### **MasterRepository** (`app/repositories/master_repository.py`):
23. `get_masters_for_service(service_id)` - Мастера для услуги
24. `get_by_id_with_services(id)` - Мастер с услугами
25. `get_master_services(master_id)` - Услуги мастера
26. `get_by_name(name)` - Мастер по имени
27. `search_by_name(search_term)` - Поиск мастеров по имени
28. `get_by_specialization(specialization)` - Мастера по специализации

### **ClientRepository** (`app/repositories/client_repository.py`):
29. `get_by_telegram_id(telegram_id)` - Клиент по Telegram ID
30. `get_or_create_by_telegram_id(telegram_id)` - Получить или создать клиента
31. `update_by_telegram_id(telegram_id, data)` - Обновление клиента
32. `search_by_name(search_term)` - Поиск клиентов по имени
33. `get_by_phone(phone_number)` - Клиент по телефону

### **ServiceRepository** (`app/repositories/service_repository.py`):
34. `get_by_name(name)` - Услуга по названию
35. `search_by_name(search_term)` - Поиск услуг по названию
36. `get_by_price_range(min_price, max_price)` - Услуги в диапазоне цен

### **MasterScheduleRepository** (`app/repositories/master_schedule_repository.py`):
37. `find_by_master_and_date(master_id, schedule_date)` - График мастера на дату
38. `get_master_schedules_for_period(master_id, start_date, end_date)` - Графики за период
39. `get_available_masters_for_date(schedule_date)` - Доступные мастера на дату
40. `create_schedule(master_id, schedule_date, start_time, end_time)` - Создание графика

### **WorkScheduleRepository** (`app/repositories/schedule_repository.py`):
41. `find_by_master_and_day(master_id, day_of_week)` - График мастера на день недели
42. `find_by_master(master_id)` - Все графики мастера
43. `find_by_master_and_date(master_id, date)` - Исключение на дату
44. `find_by_master(master_id)` - Все исключения мастера
45. `find_by_date_range(master_id, start_date, end_date)` - Исключения в диапазоне

### **DialogHistoryRepository** (`app/repositories/dialog_history_repository.py`):
46. `get_recent_messages(user_id, limit)` - Последние сообщения пользователя
47. `add_message(user_id, role, message_text)` - Добавление сообщения
48. `clear_user_history(user_id)` - Очистка истории пользователя
49. `get_message_count(user_id)` - Количество сообщений
50. `get_last_message(user_id)` - Последнее сообщение

## 🛠️ **Сервисы**

### **DbCalendarService** (`app/services/db_calendar_service.py`):
51. `get_appointments_for_masters(master_ids, target_date)` - Записи мастеров на дату

## 📊 **Итого: 51 команда обращения к YDB**

**По типам операций:**
- **SELECT запросы:** 35 команд
- **UPSERT операции:** 8 команд  
- **DELETE операции:** 3 команды
- **Управление соединениями:** 5 команд

**По таблицам:**
- `appointments` - 8 команд
- `masters` - 6 команд
- `clients` - 5 команд
- `services` - 3 команды
- `master_schedules` - 4 команды
- `work_schedules` - 3 команды
- `schedule_exceptions` - 3 команды
- `dialog_history` - 5 команд
- `master_services` - 2 команды

Все команды используют единую архитектуру через `BaseRepository` и базовые функции `execute_query`, `upsert_record`, `delete_record` из `app/core/database.py`.
