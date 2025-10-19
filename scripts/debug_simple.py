"""
Простой скрипт для отладки данных в таблице appointments.
Проверяет, что реально записалось в базу на 20 октября 2025 года.
"""

import sys
from datetime import datetime, date

# Добавляем путь к корневой папке проекта
sys.path.append('.')

from app.core.database import init_database, execute_query


def check_appointments_simple(target_date: date):
    """Проверяет все записи на целевую дату простым запросом"""
    print(f"🔍 Проверка записей на {target_date}")
    print("=" * 60)
    
    date_str = target_date.strftime('%Y-%m-%d')
    
    # Простой запрос без JOIN
    query = f"""
        SELECT id, user_telegram_id, master_id, service_id, start_time, end_time
        FROM appointments
        WHERE CAST(start_time AS Date) = CAST('{date_str}' AS Date)
        ORDER BY master_id, start_time
    """
    
    try:
        rows = execute_query(query)
        
        if not rows:
            print("❌ Записей на эту дату не найдено!")
            return
        
        print(f"✅ Найдено {len(rows)} записей:")
        print()
        
        for row in rows:
            appointment_id, user_id, master_id, service_id, start_time, end_time = row
            
            print(f"📅 ID: {appointment_id}")
            print(f"   👤 Мастер ID: {master_id}")
            print(f"   🔧 Услуга ID: {service_id}")
            print(f"   ⏰ Время: {start_time} - {end_time}")
            print(f"   👥 Клиент: {user_id}")
            print()
            
    except Exception as e:
        print(f"❌ Ошибка при получении записей: {e}")


def check_services():
    """Проверяет все услуги"""
    print("🔧 Проверка услуг")
    print("=" * 60)
    
    query = "SELECT id, name, duration_minutes FROM services ORDER BY id"
    
    try:
        rows = execute_query(query)
        
        if not rows:
            print("❌ Услуги не найдены!")
            return
        
        print(f"✅ Найдено {len(rows)} услуг:")
        print()
        
        for row in rows:
            service_id, name, duration = row
            print(f"🔧 ID: {service_id}, Название: {name}, Длительность: {duration} мин")
            
    except Exception as e:
        print(f"❌ Ошибка при получении услуг: {e}")


def check_masters():
    """Проверяет всех мастеров"""
    print("👤 Проверка мастеров")
    print("=" * 60)
    
    query = "SELECT id, name, specialization FROM masters ORDER BY id"
    
    try:
        rows = execute_query(query)
        
        if not rows:
            print("❌ Мастера не найдены!")
            return
        
        print(f"✅ Найдено {len(rows)} мастеров:")
        print()
        
        for row in rows:
            master_id, name, specialization = row
            print(f"👤 ID: {master_id}, Имя: {name}, Специализация: {specialization}")
            
    except Exception as e:
        print(f"❌ Ошибка при получении мастеров: {e}")


def main():
    """Основная функция отладки"""
    print("🔍 ПРОСТАЯ ОТЛАДКА ДАННЫХ В БАЗЕ")
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
        check_services()
        print()
        
        # Проверяем мастеров
        check_masters()
        print()
        
        # Проверяем записи
        check_appointments_simple(target_date)
        
        print("=" * 60)
        print("✅ Отладка завершена")
        
    except Exception as e:
        print(f"❌ Ошибка выполнения отладки: {e}")
        raise


if __name__ == "__main__":
    main()
