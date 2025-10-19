"""
Простая проверка созданных данных - выводим сырые данные.
"""

import sys
from datetime import datetime, date

# Добавляем путь к корневой папке проекта
sys.path.append('.')

from app.core.database import init_database, execute_query


def check_raw_data():
    """Проверяет созданные данные - выводит сырые данные"""
    print("🔍 ПРОВЕРКА СОЗДАННЫХ ДАННЫХ (СЫРЫЕ ДАННЫЕ)")
    print("=" * 60)
    
    try:
        # Простой запрос
        query = """
            SELECT id, master_id, service_id, start_time, end_time
            FROM appointments
            WHERE CAST(start_time AS Date) = CAST('2025-10-20' AS Date)
            ORDER BY master_id, start_time
        """
        
        rows = execute_query(query)
        
        if not rows:
            print("❌ Записей не найдено!")
            return
        
        print(f"✅ Найдено {len(rows)} записей:")
        print()
        
        for i, row in enumerate(rows, 1):
            appointment_id, master_id, service_id, start_time, end_time = row
            print(f"{i:2d}. ID: {appointment_id}")
            print(f"    Мастер: {master_id}")
            print(f"    Услуга: {service_id}")
            print(f"    Начало: {start_time}")
            print(f"    Конец: {end_time}")
            print()
        
        print(f"📊 ИТОГО: {len(rows)} записей")
        
        # Простая проверка по времени
        morning_count = 0
        afternoon_count = 0
        other_count = 0
        
        for row in rows:
            start_time = str(row[3])  # start_time
            if '09:' in start_time or '10:' in start_time or '11:' in start_time or '12:' in start_time:
                morning_count += 1
            elif '14:' in start_time or '15:' in start_time or '16:' in start_time or '17:' in start_time:
                afternoon_count += 1
            else:
                other_count += 1
        
        print(f"\n📊 РАСПРЕДЕЛЕНИЕ ПО ВРЕМЕНИ:")
        print(f"   🌅 Утренние слоты (9-12): {morning_count}")
        print(f"   🌆 Дневные слоты (14-17): {afternoon_count}")
        print(f"   ⚠️ Другие слоты: {other_count}")
        
        if morning_count >= 6 and afternoon_count >= 6:
            print(f"\n✅ ТЕСТОВЫЕ ДАННЫЕ СОЗДАНЫ ПРАВИЛЬНО!")
            print(f"📋 Ожидаемые свободные интервалы:")
            print(f"   • 12:30-14:30 (обеденный перерыв)")
            print(f"   • 17:00-18:30 (вечерние слоты)")
        else:
            print(f"\n⚠️ Не все тестовые данные созданы правильно")
        
    except Exception as e:
        print(f"❌ Ошибка при проверке данных: {e}")


def main():
    """Основная функция"""
    print("🔍 ПРОВЕРКА СОЗДАННЫХ ТЕСТОВЫХ ДАННЫХ")
    print("=" * 60)
    
    try:
        # Инициализация базы данных
        print("Инициализация подключения к YDB...")
        init_database()
        print("✅ Подключение к базе данных установлено")
        print()
        
        # Проверяем созданные данные
        check_raw_data()
        
        print("\n" + "=" * 60)
        print("✅ Проверка завершена")
        
    except Exception as e:
        print(f"❌ Ошибка выполнения: {e}")
        raise


if __name__ == "__main__":
    main()
