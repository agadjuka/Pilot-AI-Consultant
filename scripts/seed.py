import random
from faker import Faker
from app.core.database import get_engine, get_session_local
from app.models.service import Service
from app.models.master import Master

# Инициализация Faker для генерации русскоязычных данных
fake = Faker('ru_RU')

# Создание сессии для работы с БД
SessionLocal = get_session_local()
db = SessionLocal()

def seed_data():
    print("Starting seeding process...")

    # --- Очистка старых данных ---
    db.query(Master).delete()
    db.query(Service).delete()
    db.commit()
    print("Old data cleared.")

    # --- Создание услуг ---
    services = [
        # Парикмахерские услуги
        Service(name="Женская стрижка", price=2500, duration_minutes=60),
        Service(name="Мужская стрижка", price=1500, duration_minutes=45),
        Service(name="Окрашивание корней", price=4000, duration_minutes=120),
        Service(name="Сложное окрашивание (Airtouch)", price=9000, duration_minutes=240),
        Service(name="Укладка вечерняя", price=3000, duration_minutes=75),
        # Ногтевой сервис
        Service(name="Маникюр с покрытием гель-лак", price=2000, duration_minutes=90),
        Service(name="Педикюр", price=3000, duration_minutes=75),
        Service(name="Наращивание ногтей", price=4500, duration_minutes=150),
        # Косметология
        Service(name="Чистка лица", price=3500, duration_minutes=90),
        Service(name="Массаж лица", price=2500, duration_minutes=60),
        Service(name="Коррекция бровей", price=1000, duration_minutes=30),
        Service(name="Ламинирование ресниц", price=2800, duration_minutes=70),
    ]
    db.add_all(services)
    db.commit()
    print(f"{len(services)} services created.")

    # --- Создание мастеров ---
    masters = []
    for _ in range(10):
        masters.append(Master(name=fake.first_name_female()))
    
    db.add_all(masters)
    db.commit()

    # --- Связывание мастеров и услуг ---
    for master in masters:
        # Каждый мастер получает от 2 до 5 случайных услуг
        num_services = random.randint(2, 5)
        assigned_services = random.sample(services, num_services)
        master.services.extend(assigned_services)
    
    db.commit()
    print(f"{len(masters)} masters created and linked to services.")
    
    print("Seeding finished successfully.")


if __name__ == "__main__":
    try:
        seed_data()
    finally:
        db.close()

