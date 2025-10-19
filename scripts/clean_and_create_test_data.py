"""
Скрипт для полной очистки и создания тестовых данных на 20 октября 2025.
Сначала удаляет ВСЕ записи на эту дату, затем создает правильные тестовые данные.
"""

import sys
from datetime import datetime, date

# Добавляем путь к корневой папке проекта
sys.path.append('.')

from app.core.database import init_database, execute_query, upsert_record, delete_record
from app.repositories.appointment_repository import AppointmentRepository


def get_manicure_service_id():
    """Получает ID услуги 'Маникюр с покрытием гель-лак'"""
    query = "SELECT id FROM services WHERE name = 'Маникюр с покрытием гель-лак'"
    rows = execute_query(query)
    
    if not rows:
        raise ValueError("Услуга 'Маникюр с покрытием гель-лак' не найдена в базе данных")
    
    return rows[0][0]


def clear_ALL_appointments_on_date(target_date: date):
    """Удаляет ВСЕ записи на целевую дату"""
    print(f"🧹 ПОЛНАЯ ОЧИСТКА всех записей на {target_date}")
    print("=" * 60)
    
    date_str = target_date.strftime('%Y-%m-%d')
    
    try:
        # Сначала проверим, сколько записей есть
        count_query = f"SELECT COUNT(*) FROM appointments WHERE CAST(start_time AS Date) = CAST('{date_str}' AS Date)"
        count_rows = execute_query(count_query)
        existing_count = count_rows[0][0] if count_rows else 0
        
        print(f"📊 Найдено записей на {target_date}: {existing_count}")
        
        if existing_count == 0:
            print("✅ Записей для удаления нет")
            return
        
        # Удаляем все записи на эту дату
        delete_query = f"DELETE FROM appointments WHERE CAST(start_time AS Date) = CAST('{date_str}' AS Date)"
        delete_record("appointments", f"CAST(start_time AS Date) = CAST('{date_str}' AS Date)")
        
        print(f"✅ Удалено {existing_count} записей")
        
    except Exception as e:
        print(f"❌ Ошибка при удалении записей: {e}")
        raise


def create_appointment_with_debug(master_id: int, service_id: int, start_time: datetime, end_time: datetime, user_telegram_id: int = 999999999):
    """Создает запись в расписании с отладочной информацией"""
    try:
        repo = AppointmentRepository()
        appointment_data = {
            'user_telegram_id': user_telegram_id,
            'master_id': master_id,
            'service_id': service_id,
            'start_time': start_time,
            'end_time': end_time
        }
        
        print(f"   🔧 Создаем запись для мастера {master_id}: {start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')}")
        result = repo.create(appointment_data)
        
        if result:
            print(f"   ✅ Успешно создана запись ID: {result['id']}")
            return True
        else:
            print(f"   ❌ Не удалось создать запись")
            return False
            
    except Exception as e:
        print(f"❌ Ошибка создания записи для мастера {master_id}: {e}")
        return False


def create_morning_wall(target_date: date, service_id: int):
    """Создает утреннюю 'стену' занятых слотов (9:00-12:30)"""
    print("\n🌅 СОЗДАНИЕ УТРЕННЕЙ 'СТЕНЫ' (9:00-12:30)")
    print("-" * 50)
    
    morning_appointments = [
        # Мастер 10: 09:00-11:00
        (10, datetime(2025, 10, 20, 9, 0), datetime(2025, 10, 20, 11, 0)),
        
        # Мастер 9: 09:00-12:00
        (9, datetime(2025, 10, 20, 9, 0), datetime(2025, 10, 20, 12, 0)),
        
        # Мастер 8: 09:30-11:30
        (8, datetime(2025, 10, 20, 9, 30), datetime(2025, 10, 20, 11, 30)),
        
        # Мастер 7: 10:00-12:30
        (7, datetime(2025, 10, 20, 10, 0), datetime(2025, 10, 20, 12, 30)),
        
        # Мастер 6: 09:00-11:30
        (6, datetime(2025, 10, 20, 9, 0), datetime(2025, 10, 20, 11, 30)),
        
        # Мастер 5: 09:00-12:30
        (5, datetime(2025, 10, 20, 9, 0), datetime(2025, 10, 20, 12, 30)),
        
        # Мастер 3: 10:30-12:30
        (3, datetime(2025, 10, 20, 10, 30), datetime(2025, 10, 20, 12, 30)),
    ]
    
    created_count = 0
    for master_id, start_time, end_time in morning_appointments:
        if create_appointment_with_debug(master_id, service_id, start_time, end_time):
            created_count += 1
    
    print(f"\n📊 Утренняя 'стена' создана: {created_count}/{len(morning_appointments)} записей")
    return created_count


def create_afternoon_wall(target_date: date, service_id: int):
    """Создает дневную 'стену' занятых слотов (14:30-17:00)"""
    print("\n🌆 СОЗДАНИЕ ДНЕВНОЙ 'СТЕНЫ' (14:30-17:00)")
    print("-" * 50)
    
    afternoon_appointments = [
        # Мастер 10: 14:30-16:30
        (10, datetime(2025, 10, 20, 14, 30), datetime(2025, 10, 20, 16, 30)),
        
        # Мастер 9: 15:00-17:00
        (9, datetime(2025, 10, 20, 15, 0), datetime(2025, 10, 20, 17, 0)),
        
        # Мастер 8: 14:30-16:00
        (8, datetime(2025, 10, 20, 14, 30), datetime(2025, 10, 20, 16, 0)),
        
        # Мастер 7: 14:30-17:00
        (7, datetime(2025, 10, 20, 14, 30), datetime(2025, 10, 20, 17, 0)),
        
        # Мастер 6: 15:30-17:00
        (6, datetime(2025, 10, 20, 15, 30), datetime(2025, 10, 20, 17, 0)),
        
        # Мастер 5: 14:30-16:30
        (5, datetime(2025, 10, 20, 14, 30), datetime(2025, 10, 20, 16, 30)),
        
        # Мастер 3: 15:00-17:00
        (3, datetime(2025, 10, 20, 15, 0), datetime(2025, 10, 20, 17, 0)),
    ]
    
    created_count = 0
    for master_id, start_time, end_time in afternoon_appointments:
        if create_appointment_with_debug(master_id, service_id, start_time, end_time):
            created_count += 1
    
    print(f"\n📊 Дневная 'стена' создана: {created_count}/{len(afternoon_appointments)} записей")
    return created_count


def verify_created_data(target_date: date):
    """Проверяет созданные данные"""
    print("\n🔍 ПРОВЕРКА СОЗДАННЫХ ДАННЫХ")
    print("=" * 60)
    
    try:
        repo = AppointmentRepository()
        
        # Получаем записи в диапазоне дат
        start_datetime = datetime.combine(target_date, datetime.min.time())
        end_datetime = datetime.combine(target_date, datetime.max.time())
        
        appointments = repo.get_appointments_by_date_range(start_datetime, end_datetime)
        
        if not appointments:
            print("❌ Записей не найдено!")
            return
        
        print(f"✅ Найдено {len(appointments)} записей:")
        print()
        
        # Группируем по времени
        morning_slots = []
        afternoon_slots = []
        other_slots = []
        
        for appointment in appointments:
            start_time = appointment['start_time']
            if isinstance(start_time, str):
                start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            
            hour = start_time.hour
            
            if 9 <= hour < 13:
                morning_slots.append(appointment)
            elif 14 <= hour < 18:
                afternoon_slots.append(appointment)
            else:
                other_slots.append(appointment)
        
        print(f"🌅 Утренние слоты (9:00-12:59): {len(morning_slots)} записей")
        for slot in morning_slots:
            start_time = slot['start_time']
            end_time = slot['end_time']
            if isinstance(start_time, str):
                start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            if isinstance(end_time, str):
                end_time = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            print(f"   Мастер {slot['master_id']}: {start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')}")
        
        print(f"\n🌆 Дневные слоты (14:00-17:59): {len(afternoon_slots)} записей")
        for slot in afternoon_slots:
            start_time = slot['start_time']
            end_time = slot['end_time']
            if isinstance(start_time, str):
                start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            if isinstance(end_time, str):
                end_time = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            print(f"   Мастер {slot['master_id']}: {start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')}")
        
        if other_slots:
            print(f"\n⚠️ Другие слоты: {len(other_slots)} записей")
            for slot in other_slots:
                start_time = slot['start_time']
                end_time = slot['end_time']
                if isinstance(start_time, str):
                    start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                if isinstance(end_time, str):
                    end_time = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                print(f"   Мастер {slot['master_id']}: {start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')}")
        
    except Exception as e:
        print(f"❌ Ошибка при проверке данных: {e}")


def main():
    """Основная функция скрипта"""
    print("🚀 ПОЛНАЯ ОЧИСТКА И СОЗДАНИЕ ТЕСТОВЫХ ДАННЫХ")
    print("=" * 60)
    
    try:
        # Инициализация базы данных
        print("Инициализация подключения к YDB...")
        init_database()
        print("✅ Подключение к базе данных установлено")
        
        # Определение параметров
        target_date = date(2025, 10, 20)  # 20 октября 2025 года
        
        print(f"📅 Целевая дата: {target_date}")
        
        # Получение ID услуги
        print("\nПоиск услуги 'Маникюр с покрытием гель-лак'...")
        service_id = get_manicure_service_id()
        print(f"✅ Найден ID услуги: {service_id}")
        
        # ПОЛНАЯ ОЧИСТКА всех записей на эту дату
        clear_ALL_appointments_on_date(target_date)
        
        # Создание правильных тестовых данных
        print("\n" + "=" * 60)
        print("СОЗДАНИЕ ПРАВИЛЬНЫХ ТЕСТОВЫХ ДАННЫХ")
        print("=" * 60)
        
        morning_count = create_morning_wall(target_date, service_id)
        afternoon_count = create_afternoon_wall(target_date, service_id)
        
        total_created = morning_count + afternoon_count
        expected_total = 14  # 7 мастеров × 2 слота
        
        # Проверка созданных данных
        verify_created_data(target_date)
        
        print("\n" + "=" * 60)
        print("ИТОГОВЫЕ РЕЗУЛЬТАТЫ")
        print("=" * 60)
        print(f"📊 Всего создано записей: {total_created}/{expected_total}")
        print(f"🌅 Утренняя 'стена' (9:00-12:30): {morning_count} записей")
        print(f"🌆 Дневная 'стена' (14:30-17:00): {afternoon_count} записей")
        
        if total_created == expected_total:
            print("\n✅ Тестовые данные для 20 октября успешно созданы!")
            print("📋 Ожидаемые свободные интервалы для маникюра:")
            print("   • 12:30-14:30 (обеденный перерыв)")
            print("   • 17:00-18:30 (вечерние слоты)")
            print("\n🎯 Теперь алгоритм поиска слотов должен работать правильно!")
        else:
            print(f"\n⚠️ Создано {total_created} из {expected_total} записей. Проверьте логи.")
        
    except Exception as e:
        print(f"\n❌ Ошибка выполнения скрипта: {e}")
        raise


if __name__ == "__main__":
    main()
