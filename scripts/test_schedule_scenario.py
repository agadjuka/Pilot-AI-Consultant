#!/usr/bin/env python3
"""
Скрипт для контролируемого стресс-теста алгоритма поиска свободных слотов.

Создает "чистую" тестовую среду с определенной конфигурацией занятости
для тестирования алгоритма поиска свободных слотов.
"""

import sys
import os
from datetime import date, datetime, time
from typing import List, Dict, Any

# Добавляем корневую директорию проекта в путь
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from app.core.database import (
    get_session_pool, 
    execute_query, 
    upsert_record, 
    delete_record,
    init_database,
    close_database
)


# Шаг 1: Определение констант теста
TEST_DATE = date(2025, 10, 20)
MANICURE_MASTERS_IDS = [10, 9, 8, 7, 6, 5, 3]
MANICURE_SERVICE_ID = 6  # ID услуги "Маникюр с покрытием гель-лак"
FAKE_USER_TELEGRAM_ID = 999999999


def clear_tables():
    """Шаг 2: Подключение к БД и очистка таблиц."""
    print("🗄️ Очистка таблиц...")
    
    try:
        # Очищаем таблицу appointments
        delete_record("appointments", "1=1")  # Удаляем все записи
        print("✅ Таблица appointments очищена")
        
        # Очищаем таблицу master_schedules
        delete_record("master_schedules", "1=1")  # Удаляем все записи
        print("✅ Таблица master_schedules очищена")
        
        print("✅ Все таблицы успешно очищены")
        
    except Exception as e:
        print(f"❌ Ошибка при очистке таблиц: {e}")
        raise


def create_master_schedules():
    """Шаг 3: Создание тестовых графиков работы."""
    print("📅 Создание графиков работы мастеров...")
    
    try:
        # Получаем максимальный ID для генерации новых
        max_id_query = "SELECT MAX(id) as max_id FROM master_schedules"
        max_id_result = execute_query(max_id_query)
        max_id = max_id_result[0][0] if max_id_result[0][0] is not None else 0
        
        for i, master_id in enumerate(MANICURE_MASTERS_IDS, 1):
            schedule_data = {
                'id': max_id + i,  # Добавляем уникальный ID
                'master_id': master_id,
                'date': TEST_DATE,
                'start_time': time(10, 0),  # 10:00
                'end_time': time(18, 0)     # 18:00
            }
            
            upsert_record('master_schedules', schedule_data)
            print(f"✅ График создан для мастера {master_id} на {TEST_DATE} (10:00-18:00)")
        
        print("✅ Все графики работы созданы")
        
    except Exception as e:
        print(f"❌ Ошибка при создании графиков: {e}")
        raise


def create_test_appointments():
    """Шаг 4: Создание тестовых записей (appointments)."""
    print("📝 Создание тестовых записей...")
    
    try:
        # Получаем максимальный ID для генерации новых
        max_id_query = "SELECT MAX(id) as max_id FROM appointments"
        max_id_result = execute_query(max_id_query)
        max_id = max_id_result[0][0] if max_id_result[0][0] is not None else 0
        
        # Определяем схему занятости согласно требованиям
        appointments_data = []
        appointment_id = max_id + 1
        
        # Мастера с ID 10, 9, 8, 7, 6: две записи, с 10:00 до 12:30 и с 14:00 до 16:00
        for master_id in [10, 9, 8, 7, 6]:
            # Первая запись: 10:00-12:30
            appointments_data.append({
                'id': appointment_id,
                'user_telegram_id': FAKE_USER_TELEGRAM_ID,
                'master_id': master_id,
                'service_id': MANICURE_SERVICE_ID,
                'start_time': datetime.combine(TEST_DATE, time(10, 0)),
                'end_time': datetime.combine(TEST_DATE, time(12, 30))
            })
            appointment_id += 1
            
            # Вторая запись: 14:00-16:00
            appointments_data.append({
                'id': appointment_id,
                'user_telegram_id': FAKE_USER_TELEGRAM_ID,
                'master_id': master_id,
                'service_id': MANICURE_SERVICE_ID,
                'start_time': datetime.combine(TEST_DATE, time(14, 0)),
                'end_time': datetime.combine(TEST_DATE, time(16, 0))
            })
            appointment_id += 1
        
        # Мастер с ID 5: две записи, с 10:00 до 12:30 и с 16:00 до 17:30
        master_5_appointments = [
            {
                'id': appointment_id,
                'user_telegram_id': FAKE_USER_TELEGRAM_ID,
                'master_id': 5,
                'service_id': MANICURE_SERVICE_ID,
                'start_time': datetime.combine(TEST_DATE, time(10, 0)),
                'end_time': datetime.combine(TEST_DATE, time(12, 30))
            },
            {
                'id': appointment_id + 1,
                'user_telegram_id': FAKE_USER_TELEGRAM_ID,
                'master_id': 5,
                'service_id': MANICURE_SERVICE_ID,
                'start_time': datetime.combine(TEST_DATE, time(16, 0)),
                'end_time': datetime.combine(TEST_DATE, time(17, 30))
            }
        ]
        appointments_data.extend(master_5_appointments)
        appointment_id += 2
        
        # Мастер с ID 3: две записи, с 12:30 до 14:00 и с 14:00 до 16:00
        master_3_appointments = [
            {
                'id': appointment_id,
                'user_telegram_id': FAKE_USER_TELEGRAM_ID,
                'master_id': 3,
                'service_id': MANICURE_SERVICE_ID,
                'start_time': datetime.combine(TEST_DATE, time(12, 30)),
                'end_time': datetime.combine(TEST_DATE, time(14, 0))
            },
            {
                'id': appointment_id + 1,
                'user_telegram_id': FAKE_USER_TELEGRAM_ID,
                'master_id': 3,
                'service_id': MANICURE_SERVICE_ID,
                'start_time': datetime.combine(TEST_DATE, time(14, 0)),
                'end_time': datetime.combine(TEST_DATE, time(16, 0))
            }
        ]
        appointments_data.extend(master_3_appointments)
        
        # Создаем все записи
        for i, appointment in enumerate(appointments_data, 1):
            upsert_record('appointments', appointment)
            print(f"✅ Запись {i} создана: мастер {appointment['master_id']}, "
                  f"{appointment['start_time'].strftime('%H:%M')}-{appointment['end_time'].strftime('%H:%M')}")
        
        print("✅ Все тестовые записи созданы")
        
    except Exception as e:
        print(f"❌ Ошибка при создании записей: {e}")
        raise


def verify_test_data():
    """Проверка созданных тестовых данных."""
    print("\n🔍 Проверка созданных данных...")
    
    try:
        # Проверяем количество записей в master_schedules
        schedules_query = f"SELECT COUNT(*) FROM master_schedules WHERE date = Date('{TEST_DATE}')"
        schedules_count = execute_query(schedules_query)[0][0]
        print(f"📅 Графиков работы создано: {schedules_count}")
        
        # Проверяем количество записей в appointments
        appointments_query = f"""
            SELECT COUNT(*) FROM appointments 
            WHERE DATE(start_time) = Date('{TEST_DATE}') 
            AND service_id = {MANICURE_SERVICE_ID}
        """
        appointments_count = execute_query(appointments_query)[0][0]
        print(f"📝 Записей создано: {appointments_count}")
        
        # Показываем детали по каждому мастеру
        print("\n📊 Детализация по мастерам:")
        for master_id in MANICURE_MASTERS_IDS:
            master_appointments_query = f"""
                SELECT start_time, end_time FROM appointments 
                WHERE master_id = {master_id} 
                AND DATE(start_time) = Date('{TEST_DATE}')
                ORDER BY start_time
            """
            master_appointments = execute_query(master_appointments_query)
            
            print(f"Мастер {master_id}:")
            for appointment in master_appointments:
                start_time = appointment[0].strftime('%H:%M')
                end_time = appointment[1].strftime('%H:%M')
                print(f"  - {start_time}-{end_time}")
        
    except Exception as e:
        print(f"❌ Ошибка при проверке данных: {e}")
        raise


def main():
    """Основная функция скрипта."""
    print("🚀 Запуск скрипта тестирования сценария расписания")
    print(f"📅 Тестовая дата: {TEST_DATE}")
    print(f"👥 Мастера маникюра: {MANICURE_MASTERS_IDS}")
    print(f"💅 ID услуги маникюра: {MANICURE_SERVICE_ID}")
    print("-" * 60)
    
    try:
        # Инициализируем подключение к БД
        init_database()
        
        # Выполняем все шаги
        clear_tables()
        create_master_schedules()
        create_test_appointments()
        verify_test_data()
        
        print("\n" + "=" * 60)
        print("🎉 ТЕСТОВАЯ СРЕДА ГОТОВА!")
        print("=" * 60)
        print(f"📅 Дата тестирования: {TEST_DATE}")
        print("💅 Услуга: Маникюр с покрытием гель-лак (90 минут)")
        print("\n🎯 Ожидаемый результат для маникюра на 20.10.2025:")
        print("   Свободные слоты: 12:30-14:00, 16:00-17:30")
        print("\n📊 Схема занятости:")
        print("   Мастера 10,9,8,7,6: 10:00-12:30, 14:00-16:00")
        print("   Мастер 5: 10:00-12:30, 16:00-17:30")
        print("   Мастер 3: 12:30-14:00, 14:00-16:00")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        return 1
    
    finally:
        # Закрываем соединение с БД
        close_database()
    
    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
