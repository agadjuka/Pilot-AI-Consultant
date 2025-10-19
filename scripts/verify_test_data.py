"""
Простая проверка созданных данных через прямой запрос.
"""

import sys
from datetime import datetime, date

# Добавляем путь к корневой папке проекта
sys.path.append('.')

from app.core.database import init_database, execute_query


def check_created_data():
    """Проверяет созданные данные простым запросом"""
    print("🔍 ПРОВЕРКА СОЗДАННЫХ ДАННЫХ")
    print("=" * 60)
    
    try:
        # Простой запрос без сложных условий
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
        
        # Группируем по времени
        morning_slots = []
        afternoon_slots = []
        other_slots = []
        
        for row in rows:
            appointment_id, master_id, service_id, start_time, end_time = row
            
            # Парсим время
            if isinstance(start_time, str):
                try:
                    start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                except:
                    start_time = datetime.fromisoformat(start_time)
            
            hour = start_time.hour
            
            slot_info = {
                'id': appointment_id,
                'master_id': master_id,
                'service_id': service_id,
                'start_time': start_time,
                'end_time': end_time
            }
            
            if 9 <= hour < 13:
                morning_slots.append(slot_info)
            elif 14 <= hour < 18:
                afternoon_slots.append(slot_info)
            else:
                other_slots.append(slot_info)
        
        print(f"🌅 Утренние слоты (9:00-12:59): {len(morning_slots)} записей")
        for slot in morning_slots:
            print(f"   ID {slot['id']}: Мастер {slot['master_id']}, Услуга {slot['service_id']}, {slot['start_time'].strftime('%H:%M')} - {slot['end_time']}")
        
        print(f"\n🌆 Дневные слоты (14:00-17:59): {len(afternoon_slots)} записей")
        for slot in afternoon_slots:
            print(f"   ID {slot['id']}: Мастер {slot['master_id']}, Услуга {slot['service_id']}, {slot['start_time'].strftime('%H:%M')} - {slot['end_time']}")
        
        if other_slots:
            print(f"\n⚠️ Другие слоты: {len(other_slots)} записей")
            for slot in other_slots:
                print(f"   ID {slot['id']}: Мастер {slot['master_id']}, Услуга {slot['service_id']}, {slot['start_time'].strftime('%H:%M')} - {slot['end_time']}")
        
        print(f"\n📊 ИТОГО:")
        print(f"   • Утренние слоты: {len(morning_slots)}")
        print(f"   • Дневные слоты: {len(afternoon_slots)}")
        print(f"   • Другие слоты: {len(other_slots)}")
        print(f"   • Всего записей: {len(rows)}")
        
        if len(morning_slots) >= 6 and len(afternoon_slots) >= 6:
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
        check_created_data()
        
        print("\n" + "=" * 60)
        print("✅ Проверка завершена")
        
    except Exception as e:
        print(f"❌ Ошибка выполнения: {e}")
        raise


if __name__ == "__main__":
    main()
