"""
Скрипт для автоматического заполнения Google Calendar тестовыми записями.
Создает случайные записи для всех мастеров из базы данных.
"""
import random
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import sys
import os
from pathlib import Path

# Добавляем корневую директорию проекта в PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Устанавливаем переменную окружения для загрузки .env
os.chdir(project_root)

from app.core.database import get_session_local
from app.repositories.master_repository import MasterRepository

# Прямой импорт модуля без __init__.py
import importlib.util
spec = importlib.util.spec_from_file_location(
    "google_calendar_service",
    project_root / "app" / "services" / "google_calendar_service.py"
)
google_calendar_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(google_calendar_module)
GoogleCalendarService = google_calendar_module.GoogleCalendarService


def generate_random_time_in_range(start_date: datetime, end_date: datetime) -> datetime:
    """
    Генерирует случайное время в заданном диапазоне.
    Время выбирается в рабочие часы (с 10:00 до 19:00).
    Время создаётся с московским timezone.
    
    Args:
        start_date: Начало диапазона
        end_date: Конец диапазона
    
    Returns:
        datetime: Случайное время в диапазоне с московским timezone
    """
    # Вычисляем количество дней в диапазоне
    days_diff = (end_date - start_date).days
    
    # Выбираем случайный день
    random_day_offset = random.randint(0, days_diff)
    selected_date = start_date + timedelta(days=random_day_offset)
    
    # Выбираем случайное время в рабочем диапазоне (10:00 - 19:00)
    random_hour = random.randint(10, 18)
    random_minute = random.choice([0, 15, 30, 45])  # Кратно 15 минутам
    
    # Создаём datetime с московским timezone
    moscow_tz = ZoneInfo('Europe/Moscow')
    return selected_date.replace(
        hour=random_hour,
        minute=random_minute,
        second=0,
        microsecond=0,
        tzinfo=moscow_tz
    )


def seed_calendar():
    """
    Основная функция для заполнения календаря.
    Очищает существующие события и создает новые тестовые записи.
    """
    print("=" * 60)
    print("Запуск скрипта заполнения Google Calendar")
    print("=" * 60)
    
    # Создание сессии БД
    SessionLocal = get_session_local()
    db = SessionLocal()
    
    try:
        # Инициализация сервисов
        print("\n[1/5] Инициализация сервисов...")
        calendar_service = GoogleCalendarService()
        master_repo = MasterRepository(db)
        print("✓ Сервисы инициализированы")
        
        # Получение списка мастеров
        print("\n[2/5] Загрузка списка мастеров из БД...")
        masters = master_repo.get_all()
        if not masters:
            print("❌ В базе данных нет мастеров! Запустите сначала scripts/seed.py")
            return
        print(f"✓ Найдено мастеров: {len(masters)}")
        for master in masters:
            print(f"  - {master.name} (ID: {master.id})")
        
        # Определение временного диапазона
        now = datetime.now()
        clear_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        clear_end = clear_start + timedelta(days=30)  # Очищаем следующий месяц
        
        # Очистка календаря
        print(f"\n[3/5] Очистка календаря...")
        print(f"  Период: {clear_start.strftime('%d.%m.%Y')} - {clear_end.strftime('%d.%m.%Y')}")
        deleted_count = calendar_service.clear_calendar(
            time_min=clear_start,
            time_max=clear_end
        )
        print(f"✓ Удалено событий: {deleted_count}")
        
        # Генерация периода для новых записей (следующие 2 недели)
        records_start = clear_start
        records_end = clear_start + timedelta(days=14)
        
        # Создание записей для каждого мастера
        print(f"\n[4/5] Создание тестовых записей...")
        print(f"  Период: {records_start.strftime('%d.%m.%Y')} - {records_end.strftime('%d.%m.%Y')}")
        
        total_created = 0
        
        for master in masters:
            # Генерируем 3-4 случайных записи для каждого мастера
            num_records = random.randint(3, 4)
            print(f"\n  Мастер: {master.name}")
            
            for i in range(num_records):
                # Генерация случайного времени начала
                start_time = generate_random_time_in_range(records_start, records_end)
                
                # Случайная длительность от 60 до 120 минут
                duration_minutes = random.randint(60, 120)
                end_time = start_time + timedelta(minutes=duration_minutes)
                
                # Создание события
                event_summary = f"Запись: {master.name}"
                
                try:
                    event = calendar_service.create_event(
                        summary=event_summary,
                        start_datetime=start_time,
                        end_datetime=end_time,
                        description=f"Тестовая запись для мастера {master.name}"
                    )
                    total_created += 1
                    print(f"    ✓ Запись {i+1}: {start_time.strftime('%d.%m.%Y %H:%M')} - "
                          f"{end_time.strftime('%H:%M')} ({duration_minutes} мин)")
                except Exception as e:
                    print(f"    ❌ Ошибка при создании записи: {str(e)}")
        
        # Завершение
        print(f"\n[5/5] Завершение...")
        print(f"✓ Всего создано событий: {total_created}")
        print("\n" + "=" * 60)
        print("Заполнение календаря завершено!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {str(e)}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_calendar()

