#!/usr/bin/env python3
"""
Скрипт для заполнения таблицы appointments тестовыми данными.
Создает реалистичную занятость мастеров на ближайшие 14 дней.
"""

import random
import sys
from datetime import datetime, date, time, timedelta
from typing import List, Dict, Any, Tuple

# Добавляем путь к корневой папке проекта
sys.path.append('.')

from app.core.database import execute_query, upsert_record
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.master_repository import MasterRepository
from app.repositories.master_schedule_repository import MasterScheduleRepository


class AppointmentSeeder:
    """Класс для заполнения таблицы appointments тестовыми данными"""
    
    def __init__(self):
        self.appointment_repo = AppointmentRepository()
        self.master_repo = MasterRepository()
        self.schedule_repo = MasterScheduleRepository()
        
    def clear_appointments_table(self) -> None:
        """Проверяет таблицу appointments (без очистки для пустой таблицы)"""
        print("Проверяем таблицу appointments...")
        print("✓ Пропускаем очистку пустой таблицы для ускорения работы")
    
    def get_masters_with_schedules(self, days_ahead: int = 14) -> List[Dict[str, Any]]:
        """Получает всех мастеров с их графиками работы на указанный период"""
        print(f"Получаем мастеров и их графики на ближайшие {days_ahead} дней...")
        
        # Получаем всех мастеров
        masters_query = "SELECT * FROM masters"
        master_rows = execute_query(masters_query)
        
        masters = []
        for row in master_rows:
            master = {
                'id': row[0],
                'name': row[1].decode('utf-8') if isinstance(row[1], bytes) else str(row[1]),
                'specialization': row[2].decode('utf-8') if isinstance(row[2], bytes) else str(row[2])
            }
            
            # Получаем услуги мастера
            master['services'] = self.master_repo.get_master_services(master['id'])
            
            # Получаем графики работы на ближайшие дни
            start_date = date.today()
            end_date = start_date + timedelta(days=days_ahead)
            master['schedules'] = self.schedule_repo.get_master_schedules_for_period(
                master['id'], start_date, end_date
            )
            
            masters.append(master)
        
        print(f"✓ Найдено {len(masters)} мастеров")
        return masters
    
    def generate_random_appointments_for_master_day(
        self, 
        master: Dict[str, Any], 
        schedule: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Генерирует случайные записи для мастера на конкретный день"""
        if not master['services']:
            return []
        
        # Определяем количество записей (1-3)
        num_appointments = random.randint(1, 3)
        
        # Парсим время работы
        start_time_str = str(schedule['start_time'])
        end_time_str = str(schedule['end_time'])
        
        # Преобразуем в datetime объекты для удобства работы
        schedule_date = schedule['date']
        if isinstance(schedule_date, str):
            schedule_date = datetime.strptime(schedule_date, '%Y-%m-%d').date()
        
        start_datetime = datetime.combine(schedule_date, time.fromisoformat(start_time_str))
        end_datetime = datetime.combine(schedule_date, time.fromisoformat(end_time_str))
        
        appointments = []
        used_time_slots = []
        
        for _ in range(num_appointments):
            # Выбираем случайную услугу
            service = random.choice(master['services'])
            service_duration = timedelta(minutes=service['duration_minutes'])
            
            # Генерируем время начала, избегая пересечений
            max_attempts = 50
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
    
    def get_next_appointment_id(self) -> int:
        """Получает следующий доступный ID для записи"""
        try:
            query = "SELECT MAX(id) as max_id FROM appointments"
            result = execute_query(query)
            max_id = result[0][0] if result and result[0][0] is not None else 0
            return max_id + 1
        except Exception:
            return 1
    
    def save_appointments(self, appointments: List[Dict[str, Any]]) -> int:
        """Сохраняет записи в базу данных"""
        print(f"Сохраняем {len(appointments)} записей в базу данных...")
        
        saved_count = 0
        next_id = self.get_next_appointment_id()
        
        for appointment in appointments:
            try:
                # Добавляем ID к записи
                appointment['id'] = next_id
                upsert_record("appointments", appointment)
                next_id += 1
                saved_count += 1
            except Exception as e:
                print(f"✗ Ошибка при сохранении записи: {e}")
        
        return saved_count
    
    def run(self, days_ahead: int = 14) -> None:
        """Основной метод для запуска заполнения"""
        print("=== Заполнение таблицы appointments тестовыми данными ===")
        print(f"Период: ближайшие {days_ahead} дней")
        print()
        
        try:
            # 1. Проверяем/очищаем таблицу
            self.clear_appointments_table()
            print()
            
            # 2. Получаем мастеров с графиками
            masters = self.get_masters_with_schedules(days_ahead)
            print()
            
            # 3. Генерируем записи
            all_appointments = []
            total_schedules = 0
            
            for master in masters:
                print(f"Обрабатываем мастера: {master['name']}")
                master_appointments = 0
                
                for schedule in master['schedules']:
                    appointments = self.generate_random_appointments_for_master_day(master, schedule)
                    all_appointments.extend(appointments)
                    master_appointments += len(appointments)
                    total_schedules += 1
                
                print(f"  ✓ Создано {master_appointments} записей")
            
            print()
            print(f"Всего обработано графиков: {total_schedules}")
            print(f"Всего сгенерировано записей: {len(all_appointments)}")
            print()
            
            # 4. Сохраняем в БД
            saved_count = self.save_appointments(all_appointments)
            
            print()
            print("=== РЕЗУЛЬТАТ ===")
            print(f"✓ Успешно создано {saved_count} записей")
            print("✓ Таблица appointments заполнена тестовыми данными")
            
        except Exception as e:
            print(f"✗ Ошибка при выполнении скрипта: {e}")
            raise


def main():
    """Точка входа в скрипт"""
    try:
        seeder = AppointmentSeeder()
        seeder.run(days_ahead=14)
    except Exception as e:
        print(f"Критическая ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
