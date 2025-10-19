"""
Скрипт для отладки данных в таблице appointments.
Проверяет, что реально записалось в базу на 20 октября 2025 года.
"""

import sys
from datetime import datetime, date

# Добавляем путь к корневой папке проекта
sys.path.append('.')

from app.core.database import init_database, execute_query


def check_appointments_on_date(target_date: date):
    """Проверяет все записи на целевую дату"""
    print(f"🔍 Проверка записей на {target_date}")
    print("=" * 60)
    
    date_str = target_date.strftime('%Y-%m-%d')
    
    # Получаем все записи на эту дату
    query = f"""
        SELECT a.id, a.user_telegram_id, a.master_id, a.service_id, 
               a.start_time, a.end_time, s.name as service_name, m.name as master_name
        FROM appointments a
        JOIN services s ON a.service_id = s.id
        JOIN masters m ON a.master_id = m.id
        WHERE CAST(a.start_time AS Date) = CAST('{date_str}' AS Date)
        ORDER BY a.master_id, a.start_time
    """
    
    try:
        rows = execute_query(query)
        
        if not rows:
            print("❌ Записей на эту дату не найдено!")
            return
        
        print(f"✅ Найдено {len(rows)} записей:")
        print()
        
        for row in rows:
            appointment_id, user_id, master_id, service_id, start_time, end_time, service_name, master_name = row
            
            # Обрабатываем время
            start_time_str = str(start_time)
            end_time_str = str(end_time)
            
            print(f"📅 ID: {appointment_id}")
            print(f"   👤 Мастер: {master_name} (ID: {master_id})")
            print(f"   🔧 Услуга: {service_name}")
            print(f"   ⏰ Время: {start_time_str} - {end_time_str}")
            print(f"   👥 Клиент: {user_id}")
            print()
            
    except Exception as e:
        print(f"❌ Ошибка при получении записей: {e}")


def check_master_schedules_on_date(target_date: date, master_ids: list):
    """Проверяет графики работы мастеров на целевую дату"""
    print(f"📋 Проверка графиков работы мастеров на {target_date}")
    print("=" * 60)
    
    date_str = target_date.strftime('%Y-%m-%d')
    master_ids_str = ', '.join(map(str, master_ids))
    
    query = f"""
        SELECT ms.master_id, m.name as master_name, ms.start_time, ms.end_time
        FROM master_schedules ms
        JOIN masters m ON ms.master_id = m.id
        WHERE ms.master_id IN ({master_ids_str})
        AND CAST(ms.date AS Date) = CAST('{date_str}' AS Date)
        ORDER BY ms.master_id
    """
    
    try:
        rows = execute_query(query)
        
        if not rows:
            print("❌ Графиков работы на эту дату не найдено!")
            return
        
        print(f"✅ Найдено {len(rows)} графиков работы:")
        print()
        
        for row in rows:
            master_id, master_name, start_time, end_time = row
            print(f"👤 Мастер: {master_name} (ID: {master_id})")
            print(f"   ⏰ График: {start_time} - {end_time}")
            print()
            
    except Exception as e:
        print(f"❌ Ошибка при получении графиков: {e}")


def check_manicure_service():
    """Проверяет услугу маникюра"""
    print("🔧 Проверка услуги 'Маникюр с покрытием гель-лак'")
    print("=" * 60)
    
    query = "SELECT id, name, duration_minutes FROM services WHERE name = 'Маникюр с покрытием гель-лак'"
    
    try:
        rows = execute_query(query)
        
        if not rows:
            print("❌ Услуга не найдена!")
            return
        
        service_id, name, duration = rows[0]
        print(f"✅ Услуга найдена:")
        print(f"   ID: {service_id}")
        print(f"   Название: {name}")
        print(f"   Длительность: {duration} минут")
        print()
        
    except Exception as e:
        print(f"❌ Ошибка при получении услуги: {e}")


def main():
    """Основная функция отладки"""
    print("🔍 ОТЛАДКА ДАННЫХ В БАЗЕ")
    print("=" * 60)
    
    try:
        # Инициализация базы данных
        print("Инициализация подключения к YDB...")
        init_database()
        print("✅ Подключение к базе данных установлено")
        print()
        
        # Параметры
        target_date = date(2025, 10, 20)
        master_ids = [10, 9, 8, 7, 6, 5, 3]
        
        # Проверяем услугу
        check_manicure_service()
        
        # Проверяем графики работы
        check_master_schedules_on_date(target_date, master_ids)
        
        # Проверяем записи
        check_appointments_on_date(target_date)
        
        print("=" * 60)
        print("✅ Отладка завершена")
        
    except Exception as e:
        print(f"❌ Ошибка выполнения отладки: {e}")
        raise


if __name__ == "__main__":
    main()
