#!/usr/bin/env python3
"""
Упрощенный скрипт для заполнения таблицы appointments тестовыми данными.
"""

import random
import sys
from datetime import datetime, date, time, timedelta
from typing import List, Dict, Any

# Добавляем путь к корневой папке проекта
sys.path.append('.')

from app.core.database import execute_query, upsert_record


def get_masters_with_services() -> List[Dict[str, Any]]:
    """Получает всех мастеров с их услугами"""
    print("Получаем мастеров и их услуги...")
    
    masters_query = """
        SELECT m.id, m.name, m.specialization 
        FROM masters m
        ORDER BY m.name
    """
    master_rows = execute_query(masters_query)
    
    masters = []
    for row in master_rows:
        master = {
            'id': row[0],
            'name': row[1].decode('utf-8') if isinstance(row[1], bytes) else str(row[1]),
            'specialization': row[2].decode('utf-8') if isinstance(row[2], bytes) else str(row[2])
        }
        
        # Получаем услуги мастера
        services_query = f"""
            SELECT s.id, s.name, s.duration_minutes 
            FROM services s
            JOIN master_services ms ON s.id = ms.service_id
            WHERE ms.master_id = {master['id']}
        """
        service_rows = execute_query(services_query)
        
        master['services'] = []
        for service_row in service_rows:
            master['services'].append({
                'id': service_row[0],
                'name': service_row[1].decode('utf-8') if isinstance(service_row[1], bytes) else str(service_row[1]),
                'duration_minutes': service_row[2]
            })
        
        masters.append(master)
    
    print(f"✓ Найдено {len(masters)} мастеров")
    return masters


def get_master_schedules(master_id: int, days_ahead: int = 14) -> List[Dict[str, Any]]:
    """Получает графики работы мастера на ближайшие дни"""
    start_date = date.today()
    end_date = start_date + timedelta(days=days_ahead)
    
    query = f"""
        SELECT date, start_time, end_time 
        FROM master_schedules 
        WHERE master_id = {master_id} 
        AND date >= Date('{start_date}') 
        AND date <= Date('{end_date}')
        ORDER BY date
    """
    rows = execute_query(query)
    
    schedules = []
    for row in rows:
        schedules.append({
            'date': row[0],
            'start_time': row[1],
            'end_time': row[2]
        })
    
    return schedules


def generate_appointments_for_master_day(master: Dict[str, Any], schedule: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Генерирует случайные записи для мастера на конкретный день"""
    if not master['services']:
        return []
    
    # Определяем количество записей (1-3)
    num_appointments = random.randint(1, 3)
    
    # Парсим время работы
    start_time_str = str(schedule['start_time'])
    end_time_str = str(schedule['end_time'])
    
    # Очищаем от bytes префикса
    if start_time_str.startswith("b'"):
        start_time_str = start_time_str[2:-1]
    if end_time_str.startswith("b'"):
        end_time_str = end_time_str[2:-1]
    
    # Преобразуем в datetime объекты
    schedule_date = schedule['date']
    if isinstance(schedule_date, str):
        schedule_date = datetime.strptime(schedule_date, '%Y-%m-%d').date()
    elif isinstance(schedule_date, int):
        # Если дата приходит как int (дни с эпохи), конвертируем правильно
        # YDB возвращает даты как количество дней с 1970-01-01
        epoch = date(1970, 1, 1)
        schedule_date = epoch + timedelta(days=schedule_date)
    
    start_datetime = datetime.combine(schedule_date, time.fromisoformat(start_time_str))
    end_datetime = datetime.combine(schedule_date, time.fromisoformat(end_time_str))
    
    appointments = []
    used_time_slots = []
    
    for _ in range(num_appointments):
        # Выбираем случайную услугу
        service = random.choice(master['services'])
        service_duration = timedelta(minutes=service['duration_minutes'])
        
        # Генерируем время начала, избегая пересечений
        max_attempts = 20
        for attempt in range(max_attempts):
            # Генерируем случайное время начала в пределах рабочего дня
            time_range = end_datetime - start_datetime - service_duration
            if time_range.total_seconds() <= 0:
                break  # Не хватает времени для услуги
            
            random_minutes = random.randint(0, int(time_range.total_seconds() / 60))
            appointment_start = start_datetime + timedelta(minutes=random_minutes)
            appointment_end = appointment_start + service_duration
            
            # Проверяем, что время не выходит за границы рабочего дня
            if appointment_end > end_datetime:
                continue
            
            # Проверяем пересечения с уже созданными записями
            has_conflict = False
            for used_start, used_end in used_time_slots:
                if (appointment_start < used_end and appointment_end > used_start):
                    has_conflict = True
                    break
            
            if not has_conflict:
                # Создаем запись
                appointment = {
                    'user_telegram_id': random.randint(100000000, 999999999),
                    'master_id': master['id'],
                    'service_id': service['id'],
                    'start_time': appointment_start,
                    'end_time': appointment_end
                }
                appointments.append(appointment)
                used_time_slots.append((appointment_start, appointment_end))
                break
    
    return appointments


def get_next_appointment_id() -> int:
    """Получает следующий доступный ID для записи"""
    try:
        query = "SELECT MAX(id) as max_id FROM appointments"
        result = execute_query(query)
        max_id = result[0][0] if result and result[0][0] is not None else 0
        return max_id + 1
    except Exception:
        return 1


def main():
    """Основная функция"""
    print("=== Заполнение таблицы appointments тестовыми данными ===")
    print("Период: ближайшие 14 дней")
    print()
    
    try:
        # Получаем мастеров с услугами
        masters = get_masters_with_services()
        print()
        
        # Генерируем записи
        all_appointments = []
        next_id = get_next_appointment_id()
        
        for master in masters:
            print(f"Обрабатываем мастера: {master['name']}")
            master_appointments = 0
            
            # Получаем графики работы мастера
            schedules = get_master_schedules(master['id'])
            
            for schedule in schedules:
                appointments = generate_appointments_for_master_day(master, schedule)
                all_appointments.extend(appointments)
                master_appointments += len(appointments)
            
            print(f"  ✓ Создано {master_appointments} записей")
        
        print()
        print(f"Всего сгенерировано записей: {len(all_appointments)}")
        print()
        
        # Сохраняем в БД
        print("Сохраняем записи в базу данных...")
        saved_count = 0
        
        for appointment in all_appointments:
            try:
                appointment['id'] = next_id
                upsert_record("appointments", appointment)
                next_id += 1
                saved_count += 1
            except Exception as e:
                print(f"✗ Ошибка при сохранении записи: {e}")
        
        print()
        print("=== РЕЗУЛЬТАТ ===")
        print(f"✓ Успешно создано {saved_count} записей")
        print("✓ Таблица appointments заполнена тестовыми данными")
        
    except Exception as e:
        print(f"✗ Ошибка при выполнении скрипта: {e}")
        raise


if __name__ == "__main__":
    main()
