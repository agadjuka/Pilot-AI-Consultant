"""
Скрипт для проверки конкретных записей на 20 октября.
Проверяет записи для мастеров маникюра.
"""

import sys
from datetime import datetime, date

# Добавляем путь к корневой папке проекта
sys.path.append('.')

from app.core.database import init_database
from app.repositories.appointment_repository import AppointmentRepository


def check_specific_masters(target_date: date, master_ids: list):
    """Проверяет записи для конкретных мастеров"""
    print(f"🔍 Проверка записей для мастеров {master_ids} на {target_date}")
    print("=" * 60)
    
    try:
        repo = AppointmentRepository()
        
        for master_id in master_ids:
            print(f"\n👤 Мастер ID: {master_id}")
            appointments = repo.get_appointments_by_master(master_id, target_date)
            
            if not appointments:
                print("   ❌ Записей не найдено")
                continue
            
            print(f"   ✅ Найдено {len(appointments)} записей:")
            
            for appointment in appointments:
                print(f"      📅 ID: {appointment['id']}")
                print(f"         🔧 Услуга ID: {appointment['service_id']}")
                print(f"         ⏰ Время: {appointment['start_time']} - {appointment['end_time']}")
                print(f"         👥 Клиент: {appointment['user_telegram_id']}")
                print()
                
    except Exception as e:
        print(f"❌ Ошибка при получении записей: {e}")


def main():
    """Основная функция"""
    print("🔍 ПРОВЕРКА ЗАПИСЕЙ ДЛЯ МАСТЕРОВ МАНИКЮРА")
    print("=" * 60)
    
    try:
        # Инициализация базы данных
        print("Инициализация подключения к YDB...")
        init_database()
        print("✅ Подключение к базе данных установлено")
        print()
        
        # Параметры
        target_date = date(2025, 10, 20)
        
        # Проверяем мастеров, для которых мы создавали записи
        test_master_ids = [10, 9, 8, 7, 6, 5, 3]
        print("Проверяем мастеров из тестового скрипта:")
        check_specific_masters(target_date, test_master_ids)
        
        print("\n" + "=" * 60)
        print("Проверяем реальных мастеров маникюра:")
        real_manicure_masters = [7, 9, 10]  # Октябрина, Акулина, Прасковья
        check_specific_masters(target_date, real_manicure_masters)
        
        print("=" * 60)
        print("✅ Проверка завершена")
        
    except Exception as e:
        print(f"❌ Ошибка выполнения: {e}")
        raise


if __name__ == "__main__":
    main()
