import random
from datetime import date, timedelta, time
from faker import Faker
from app.core.database import init_database, execute_query, upsert_record
from app.repositories.master_schedule_repository import MasterScheduleRepository

# Инициализация Faker для генерации русскоязычных данных
fake = Faker('ru_RU')

def seed_data():
    print("Starting seeding process...")

    # --- Очистка старых данных ---
    try:
        execute_query("DELETE FROM master_schedules")
        execute_query("DELETE FROM master_services")
        execute_query("DELETE FROM masters")
        execute_query("DELETE FROM services")
        print("Old data cleared.")
    except Exception as e:
        print(f"Warning: Error clearing old data: {e}")

    # --- Создание услуг ---
    services_data = [
        # Парикмахерские услуги
        {"name": "Женская стрижка", "description": "Стрижка для женщин", "price": 2500.0, "duration_minutes": 60},
        {"name": "Мужская стрижка", "description": "Стрижка для мужчин", "price": 1500.0, "duration_minutes": 45},
        {"name": "Окрашивание корней", "description": "Окрашивание корней волос", "price": 4000.0, "duration_minutes": 120},
        {"name": "Сложное окрашивание (Airtouch)", "description": "Сложное окрашивание", "price": 9000.0, "duration_minutes": 240},
        {"name": "Укладка вечерняя", "description": "Вечерняя укладка", "price": 3000.0, "duration_minutes": 75},
        # Ногтевой сервис
        {"name": "Маникюр с покрытием гель-лак", "description": "Маникюр с гель-лаком", "price": 2000.0, "duration_minutes": 90},
        {"name": "Педикюр", "description": "Педикюр", "price": 3000.0, "duration_minutes": 75},
        {"name": "Наращивание ногтей", "description": "Наращивание ногтей", "price": 4500.0, "duration_minutes": 150},
        # Косметология
        {"name": "Чистка лица", "description": "Чистка лица", "price": 3500.0, "duration_minutes": 90},
        {"name": "Массаж лица", "description": "Массаж лица", "price": 2500.0, "duration_minutes": 60},
        {"name": "Коррекция бровей", "description": "Коррекция бровей", "price": 1000.0, "duration_minutes": 30},
        {"name": "Ламинирование ресниц", "description": "Ламинирование ресниц", "price": 2800.0, "duration_minutes": 70},
    ]
    
    service_ids = []
    for i, service in enumerate(services_data, 1):
        service['id'] = i
        upsert_record('services', service)
        service_ids.append(i)
    
    print(f"{len(services_data)} services created.")

    # --- Создание мастеров ---
    masters_data = []
    for i in range(1, 11):
        master_data = {
            'id': i,
            'name': fake.first_name_female(),
            'specialization': random.choice(['Парикмахер', 'Мастер маникюра', 'Косметолог', 'Мастер по бровям'])
        }
        upsert_record('masters', master_data)
        masters_data.append(master_data)

    print(f"{len(masters_data)} masters created.")

    # --- Связывание мастеров и услуг ---
    master_service_links = []
    for master in masters_data:
        # Каждый мастер получает от 2 до 5 случайных услуг
        num_services = random.randint(2, 5)
        assigned_service_ids = random.sample(service_ids, num_services)
        
        for service_id in assigned_service_ids:
            link_data = {
                'master_id': master['id'],
                'service_id': service_id
            }
            master_service_links.append(link_data)
            upsert_record('master_services', link_data)
    
    print(f"{len(master_service_links)} master-service links created.")

    # --- Создание графиков работы на ближайшие 14 дней ---
    today = date.today()
    schedules_created = 0
    
    # Собираем все графики в один список
    schedules_data = []
    for master in masters_data:
        for day in range(14):
            schedule_date = today + timedelta(days=day)
            
            # С вероятностью ~80% считаем день рабочим
            if random.random() < 0.8:
                # Генерируем случайное время начала (с 9:00 до 12:00)
                start_hour = random.randint(9, 12)
                start_minute = random.choice([0, 30])
                start_time = f"{start_hour:02d}:{start_minute:02d}"
                
                # Генерируем случайное время окончания (с 17:00 до 20:00)
                end_hour = random.randint(17, 20)
                end_minute = random.choice([0, 30])
                end_time = f"{end_hour:02d}:{end_minute:02d}"
                
                # Добавляем в список для пакетной вставки
                schedules_data.append({
                    'master_id': master['id'],
                    'date': schedule_date,
                    'start_time': start_time,
                    'end_time': end_time
                })
    
    # Вставляем все графики пакетно
    for i, schedule_data in enumerate(schedules_data, 1):
        schedule_data['id'] = i
        upsert_record('master_schedules', schedule_data)
        schedules_created += 1
    
    print(f"{schedules_created} work schedules created for the next 14 days.")
    
    print("Seeding finished successfully.")


if __name__ == "__main__":
    try:
        # Инициализируем базу данных
        init_database()
        print("Database initialized.")
        
        # Заполняем данными
        seed_data()
    except Exception as e:
        print(f"Error during seeding: {e}")
        raise

