"""
Скрипт для отладки через репозиторий.
Проверяет данные через AppointmentRepository.
"""

import sys
from datetime import datetime, date

# Добавляем путь к корневой папке проекта
sys.path.append('.')

from app.core.database import init_database
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.master_repository import MasterRepository
from app.repositories.service_repository import ServiceRepository


def check_appointments_via_repo(target_date: date):
    """Проверяет записи через репозиторий"""
    print(f"🔍 Проверка записей через репозиторий на {target_date}")
    print("=" * 60)
    
    try:
        repo = AppointmentRepository()
        
        # Получаем записи в диапазоне дат
        start_datetime = datetime.combine(target_date, datetime.min.time())
        end_datetime = datetime.combine(target_date, datetime.max.time())
        
        appointments = repo.get_appointments_by_date_range(start_datetime, end_datetime)
        
        if not appointments:
            print("❌ Записей на эту дату не найдено!")
            return
        
        print(f"✅ Найдено {len(appointments)} записей:")
        print()
        
        for appointment in appointments:
            print(f"📅 ID: {appointment['id']}")
            print(f"   👤 Мастер ID: {appointment['master_id']}")
            print(f"   🔧 Услуга ID: {appointment['service_id']}")
            print(f"   ⏰ Время: {appointment['start_time']} - {appointment['end_time']}")
            print(f"   👥 Клиент: {appointment['user_telegram_id']}")
            print()
            
    except Exception as e:
        print(f"❌ Ошибка при получении записей: {e}")


def check_services_via_repo():
    """Проверяет услуги через репозиторий"""
    print("🔧 Проверка услуг через репозиторий")
    print("=" * 60)
    
    try:
        repo = ServiceRepository()
        services = repo.get_all()
        
        if not services:
            print("❌ Услуги не найдены!")
            return
        
        print(f"✅ Найдено {len(services)} услуг:")
        print()
        
        for service in services:
            print(f"🔧 ID: {service['id']}, Название: {service['name']}, Длительность: {service['duration_minutes']} мин")
            
    except Exception as e:
        print(f"❌ Ошибка при получении услуг: {e}")


def check_masters_via_repo():
    """Проверяет мастеров через репозиторий"""
    print("👤 Проверка мастеров через репозиторий")
    print("=" * 60)
    
    try:
        repo = MasterRepository()
        masters = repo.get_all()
        
        if not masters:
            print("❌ Мастера не найдены!")
            return
        
        print(f"✅ Найдено {len(masters)} мастеров:")
        print()
        
        for master in masters:
            print(f"👤 ID: {master['id']}, Имя: {master['name']}, Специализация: {master['specialization']}")
            
    except Exception as e:
        print(f"❌ Ошибка при получении мастеров: {e}")


def main():
    """Основная функция отладки"""
    print("🔍 ОТЛАДКА ЧЕРЕЗ РЕПОЗИТОРИИ")
    print("=" * 60)
    
    try:
        # Инициализация базы данных
        print("Инициализация подключения к YDB...")
        init_database()
        print("✅ Подключение к базе данных установлено")
        print()
        
        # Параметры
        target_date = date(2025, 10, 20)
        
        # Проверяем услуги
        check_services_via_repo()
        print()
        
        # Проверяем мастеров
        check_masters_via_repo()
        print()
        
        # Проверяем записи
        check_appointments_via_repo(target_date)
        
        print("=" * 60)
        print("✅ Отладка завершена")
        
    except Exception as e:
        print(f"❌ Ошибка выполнения отладки: {e}")
        raise


if __name__ == "__main__":
    main()
