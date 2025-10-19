"""
Исправленный скрипт для создания тестовых данных расписания.
Создает записи с правильным временем для тестирования алгоритма поиска слотов.
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


def clear_existing_appointments(target_date: date, master_ids: list):
    """Удаляет все существующие записи для указанных мастеров на целевую дату"""
    print(f"Очистка существующих записей на {target_date} для мастеров {master_ids}...")
    
    # Формируем условие для удаления
    master_ids_str = ', '.join(map(str, master_ids))
    date_str = target_date.strftime('%Y-%m-%d')
    
    try:
        delete_record("appointments", f"master_id IN ({master_ids_str}) AND CAST(start_time AS Date) = CAST('{date_str}' AS Date)")
        print("✅ Существующие записи удалены")
    except Exception as e:
        print(f"⚠️ Ошибка при удалении записей: {e}")


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
        
        print(f"   🔧 Создаем запись для мастера {master_id}: {start_time} - {end_time}")
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


def create_morning_wall_fixed(target_date: date, service_id: int):
    """Создает утреннюю 'стену' занятых слотов (9:00-12:30) с правильным временем"""
    print("Создание утренней 'стены' занятых слотов...")
    
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
    
    print(f"Утренняя 'стена' создана: {created_count}/{len(morning_appointments)} записей")
    return created_count


def create_afternoon_wall_fixed(target_date: date, service_id: int):
    """Создает дневную 'стену' занятых слотов (14:30-17:00) с правильным временем"""
    print("Создание дневной 'стены' занятых слотов...")
    
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
    
    print(f"Дневная 'стена' создана: {created_count}/{len(afternoon_appointments)} записей")
    return created_count


def main():
    """Основная функция скрипта"""
    print("🚀 Запуск ИСПРАВЛЕННОГО скрипта создания тестовых данных расписания")
    print("=" * 60)
    
    try:
        # Инициализация базы данных
        print("Инициализация подключения к YDB...")
        init_database()
        print("✅ Подключение к базе данных установлено")
        
        # Определение параметров
        target_date = date(2025, 10, 20)  # 20 октября 2025 года
        master_ids = [10, 9, 8, 7, 6, 5, 3]  # ID мастеров маникюра
        
        print(f"📅 Целевая дата: {target_date}")
        print(f"👥 Мастера маникюра: {master_ids}")
        
        # Получение ID услуги
        print("Поиск услуги 'Маникюр с покрытием гель-лак'...")
        service_id = get_manicure_service_id()
        print(f"✅ Найден ID услуги: {service_id}")
        
        # Очистка существующих записей
        clear_existing_appointments(target_date, master_ids)
        
        # Создание занятых слотов
        print("\n" + "=" * 60)
        print("СОЗДАНИЕ ЗАНЯТЫХ СЛОТОВ С ПРАВИЛЬНЫМ ВРЕМЕНЕМ")
        print("=" * 60)
        
        morning_count = create_morning_wall_fixed(target_date, service_id)
        afternoon_count = create_afternoon_wall_fixed(target_date, service_id)
        
        total_created = morning_count + afternoon_count
        expected_total = 14  # 7 мастеров × 2 слота
        
        print("\n" + "=" * 60)
        print("РЕЗУЛЬТАТЫ")
        print("=" * 60)
        print(f"📊 Всего создано записей: {total_created}/{expected_total}")
        print(f"🌅 Утренняя 'стена' (9:00-12:30): {morning_count} записей")
        print(f"🌆 Дневная 'стена' (14:30-17:00): {afternoon_count} записей")
        
        if total_created == expected_total:
            print("\n✅ Тестовые данные для 20 октября успешно созданы.")
            print("📋 Ожидаемые свободные интервалы для маникюра:")
            print("   • 12:30-14:30 (обеденный перерыв)")
            print("   • 17:00-18:30 (вечерние слоты)")
        else:
            print(f"\n⚠️ Создано {total_created} из {expected_total} записей. Проверьте логи.")
        
    except Exception as e:
        print(f"\n❌ Ошибка выполнения скрипта: {e}")
        raise


if __name__ == "__main__":
    main()
