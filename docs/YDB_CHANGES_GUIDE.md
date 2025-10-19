# Руководство по внесению изменений в YDB

## Общие принципы

При работе с YDB важно помнить:
- Все изменения выполняются через транзакции
- Обязательно используйте явный коммит транзакций
- Всегда обрабатывайте ошибки с откатом транзакций
- Используйте подготовленные запросы для безопасности

## Добавление новых записей

### Добавление услуги

```python
def add_service(session, name, description, price, duration_minutes):
    """Добавляет новую услугу в базу данных"""
    tx = session.transaction()
    try:
        # Получаем следующий ID
        prepared = session.prepare("SELECT MAX(id) as max_id FROM services")
        result = session.transaction().execute(prepared)
        max_id = result[0].rows[0][0] if result[0].rows[0][0] is not None else 0
        new_id = max_id + 1
        
        # Добавляем услугу
        query = f"""
            UPSERT INTO services (id, name, description, price, duration_minutes)
            VALUES ({new_id}, '{name.replace("'", "''")}', '{description.replace("'", "''")}', {price}, {duration_minutes})
        """
        prepared = session.prepare(query)
        tx.execute(prepared)
        tx.commit()
        return new_id
    except Exception as e:
        tx.rollback()
        raise e
```

### Добавление мастера

```python
def add_master(session, name, specialization=""):
    """Добавляет нового мастера в базу данных"""
    tx = session.transaction()
    try:
        # Получаем следующий ID
        prepared = session.prepare("SELECT MAX(id) as max_id FROM masters")
        result = session.transaction().execute(prepared)
        max_id = result[0].rows[0][0] if result[0].rows[0][0] is not None else 0
        new_id = max_id + 1
        
        # Добавляем мастера
        query = f"""
            UPSERT INTO masters (id, name, specialization)
            VALUES ({new_id}, '{name.replace("'", "''")}', '{specialization.replace("'", "''")}')
        """
        prepared = session.prepare(query)
        tx.execute(prepared)
        tx.commit()
        return new_id
    except Exception as e:
        tx.rollback()
        raise e
```

### Добавление клиента

```python
def add_client(session, telegram_id, first_name="", phone_number=""):
    """Добавляет нового клиента в базу данных"""
    tx = session.transaction()
    try:
        # Проверяем, существует ли клиент
        prepared = session.prepare(f"SELECT id FROM clients WHERE telegram_id = {telegram_id}")
        result = session.transaction().execute(prepared)
        
        if result[0].rows:
            # Клиент уже существует, обновляем данные
            client_id = result[0].rows[0][0]
            query = f"""
                UPDATE clients 
                SET first_name = '{first_name.replace("'", "''")}', 
                    phone_number = '{phone_number.replace("'", "''")}'
                WHERE id = {client_id}
            """
        else:
            # Новый клиент
            prepared = session.prepare("SELECT MAX(id) as max_id FROM clients")
            result = session.transaction().execute(prepared)
            max_id = result[0].rows[0][0] if result[0].rows[0][0] is not None else 0
            client_id = max_id + 1
            
            query = f"""
                UPSERT INTO clients (id, telegram_id, first_name, phone_number)
                VALUES ({client_id}, {telegram_id}, '{first_name.replace("'", "''")}', '{phone_number.replace("'", "''")}')
            """
        
        prepared = session.prepare(query)
        tx.execute(prepared)
        tx.commit()
        return client_id
    except Exception as e:
        tx.rollback()
        raise e
```

## Связывание мастеров и услуг

### Назначение услуги мастеру

```python
def assign_service_to_master(session, master_id, service_id):
    """Назначает услугу мастеру"""
    tx = session.transaction()
    try:
        query = f"""
            UPSERT INTO master_services (master_id, service_id)
            VALUES ({master_id}, {service_id})
        """
        prepared = session.prepare(query)
        tx.execute(prepared)
        tx.commit()
    except Exception as e:
        tx.rollback()
        raise e
```

### Удаление услуги у мастера

```python
def remove_service_from_master(session, master_id, service_id):
    """Удаляет услугу у мастера"""
    tx = session.transaction()
    try:
        query = f"""
            DELETE FROM master_services 
            WHERE master_id = {master_id} AND service_id = {service_id}
        """
        prepared = session.prepare(query)
        tx.execute(prepared)
        tx.commit()
    except Exception as e:
        tx.rollback()
        raise e
```

## Создание записей на услуги

### Добавление записи

```python
def add_appointment(session, user_telegram_id, master_id, service_id, start_time, end_time):
    """Добавляет запись на услугу"""
    tx = session.transaction()
    try:
        # Получаем следующий ID
        prepared = session.prepare("SELECT MAX(id) as max_id FROM appointments")
        result = session.transaction().execute(prepared)
        max_id = result[0].rows[0][0] if result[0].rows[0][0] is not None else 0
        new_id = max_id + 1
        
        # Конвертируем время в правильный формат
        if isinstance(start_time, str):
            start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
        if isinstance(end_time, str):
            end_time = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
        
        query = f"""
            UPSERT INTO appointments (id, user_telegram_id, master_id, service_id, start_time, end_time)
            VALUES ({new_id}, {user_telegram_id}, {master_id}, {service_id}, '{start_time.isoformat()}', '{end_time.isoformat()}')
        """
        prepared = session.prepare(query)
        tx.execute(prepared)
        tx.commit()
        return new_id
    except Exception as e:
        tx.rollback()
        raise e
```

## Обновление существующих записей

### Обновление услуги

```python
def update_service(session, service_id, **kwargs):
    """Обновляет данные услуги"""
    tx = session.transaction()
    try:
        updates = []
        if 'name' in kwargs:
            updates.append(f"name = '{kwargs['name'].replace("'", "''")}'")
        if 'description' in kwargs:
            updates.append(f"description = '{kwargs['description'].replace("'", "''")}'")
        if 'price' in kwargs:
            updates.append(f"price = {kwargs['price']}")
        if 'duration_minutes' in kwargs:
            updates.append(f"duration_minutes = {kwargs['duration_minutes']}")
        
        if updates:
            query = f"""
                UPDATE services 
                SET {', '.join(updates)}
                WHERE id = {service_id}
            """
            prepared = session.prepare(query)
            tx.execute(prepared)
            tx.commit()
    except Exception as e:
        tx.rollback()
        raise e
```

### Обновление мастера

```python
def update_master(session, master_id, **kwargs):
    """Обновляет данные мастера"""
    tx = session.transaction()
    try:
        updates = []
        if 'name' in kwargs:
            updates.append(f"name = '{kwargs['name'].replace("'", "''")}'")
        if 'specialization' in kwargs:
            updates.append(f"specialization = '{kwargs['specialization'].replace("'", "''")}'")
        
        if updates:
            query = f"""
                UPDATE masters 
                SET {', '.join(updates)}
                WHERE id = {master_id}
            """
            prepared = session.prepare(query)
            tx.execute(prepared)
            tx.commit()
    except Exception as e:
        tx.rollback()
        raise e
```

## Удаление записей

### Удаление услуги

```python
def delete_service(session, service_id):
    """Удаляет услугу и все связанные записи"""
    tx = session.transaction()
    try:
        # Удаляем связи с мастерами
        query = f"DELETE FROM master_services WHERE service_id = {service_id}"
        prepared = session.prepare(query)
        tx.execute(prepared)
        
        # Удаляем услугу
        query = f"DELETE FROM services WHERE id = {service_id}"
        prepared = session.prepare(query)
        tx.execute(prepared)
        
        tx.commit()
    except Exception as e:
        tx.rollback()
        raise e
```

### Удаление мастера

```python
def delete_master(session, master_id):
    """Удаляет мастера и все связанные записи"""
    tx = session.transaction()
    try:
        # Удаляем связи с услугами
        query = f"DELETE FROM master_services WHERE master_id = {master_id}"
        prepared = session.prepare(query)
        tx.execute(prepared)
        
        # Удаляем записи на услуги
        query = f"DELETE FROM appointments WHERE master_id = {master_id}"
        prepared = session.prepare(query)
        tx.execute(prepared)
        
        # Удаляем мастера
        query = f"DELETE FROM masters WHERE id = {master_id}"
        prepared = session.prepare(query)
        tx.execute(prepared)
        
        tx.commit()
    except Exception as e:
        tx.rollback()
        raise e
```

## Получение данных

### Получение всех услуг

```python
def get_all_services(session):
    """Возвращает все услуги"""
    prepared = session.prepare("SELECT * FROM services ORDER BY name")
    result = session.transaction().execute(prepared)
    return result[0].rows
```

### Получение услуг мастера

```python
def get_master_services(session, master_id):
    """Возвращает услуги конкретного мастера"""
    query = f"""
        SELECT s.* FROM services s
        JOIN master_services ms ON s.id = ms.service_id
        WHERE ms.master_id = {master_id}
        ORDER BY s.name
    """
    prepared = session.prepare(query)
    result = session.transaction().execute(prepared)
    return result[0].rows
```

### Получение свободных слотов мастера

```python
def get_master_free_slots(session, master_id, date):
    """Возвращает свободные слоты мастера на дату"""
    query = f"""
        SELECT start_time, end_time FROM appointments
        WHERE master_id = {master_id}
        AND DATE(start_time) = '{date}'
        ORDER BY start_time
    """
    prepared = session.prepare(query)
    result = session.transaction().execute(prepared)
    return result[0].rows
```

## Примеры использования

### Полный пример работы с базой данных

```python
import ydb
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()

# Настройки подключения
driver_config = ydb.DriverConfig(
    endpoint=os.getenv("YDB_ENDPOINT"),
    database=os.getenv("YDB_DATABASE"),
    credentials=ydb.iam.ServiceAccountCredentials.from_file("key.json"),
)

def main():
    with ydb.Driver(driver_config) as driver:
        driver.wait(timeout=5, fail_fast=True)
        
        with ydb.SessionPool(driver) as pool:
            # Добавляем новую услугу
            service_id = pool.retry_operation_sync(
                add_service, 
                "Новая услуга", 
                "Описание новой услуги", 
                3000.0, 
                90
            )
            print(f"Добавлена услуга с ID: {service_id}")
            
            # Добавляем нового мастера
            master_id = pool.retry_operation_sync(
                add_master, 
                "Новый мастер", 
                "Парикмахер"
            )
            print(f"Добавлен мастер с ID: {master_id}")
            
            # Назначаем услугу мастеру
            pool.retry_operation_sync(
                assign_service_to_master, 
                master_id, 
                service_id
            )
            print("Услуга назначена мастеру")
            
            # Получаем все услуги
            services = pool.retry_operation_sync(get_all_services)
            print(f"Всего услуг: {len(services)}")

if __name__ == "__main__":
    main()
```

## Обработка ошибок

Всегда используйте try/catch блоки при работе с базой данных:

```python
try:
    with ydb.Driver(driver_config) as driver:
        driver.wait(timeout=5, fail_fast=True)
        with ydb.SessionPool(driver) as pool:
            # Ваш код
            pass
except ydb.issues.GenericError as e:
    print(f"Ошибка YDB: {e}")
except Exception as e:
    print(f"Общая ошибка: {e}")
```

## Рекомендации

1. **Всегда используйте транзакции** для изменения данных
2. **Экранируйте пользовательский ввод** для предотвращения SQL-инъекций
3. **Используйте UPSERT** вместо INSERT для избежания дублирования
4. **Проверяйте существование записей** перед удалением связанных данных
5. **Логируйте все операции** для отладки и мониторинга
6. **Используйте индексы** для оптимизации запросов (если необходимо)
