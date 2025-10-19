#!/usr/bin/env python3
"""
Алгоритм генерации расписания на ближайшую неделю для всех услуг.

Создает реалистичное расписание где:
- Каждый мастер занят одной услугой с 10:00 до 18:00
- У каждой услуги на каждый день разное время
- Иногда есть свободные слоты по 3 часа
- Применяется принцип из test_schedule_scenario.py
"""

import sys
import os
import random
from datetime import date, datetime, time, timedelta
from typing import List, Dict, Any, Tuple

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


class WeeklyScheduleGenerator:
    """Генератор расписания на неделю для всех услуг"""
    
    def __init__(self):
        self.fake_user_telegram_id = 999999999
        self.start_date = date.today() + timedelta(days=1)  # Завтра
        self.end_date = self.start_date + timedelta(days=6)  # Неделя
        
    def get_all_services(self) -> List[Dict]:
        """Получает все услуги из базы данных"""
        query = "SELECT id, name, duration_minutes FROM services ORDER BY id"
        result = execute_query(query)
        
        services = []
        for row in result:
            # Декодируем имя услуги если оно в байтах
            name = row[1]
            if isinstance(name, bytes):
                name = name.decode('utf-8')
            
            services.append({
                'id': row[0],
                'name': name,
                'duration_minutes': row[2]
            })
        
        print(f"📋 Найдено услуг: {len(services)}")
        for service in services:
            print(f"   - {service['name']} (ID: {service['id']}, {service['duration_minutes']} мин)")
        
        return services
    
    def get_all_masters(self) -> List[Dict]:
        """Получает всех мастеров из базы данных"""
        query = "SELECT id, name, specialization FROM masters ORDER BY id"
        result = execute_query(query)
        
        masters = []
        for row in result:
            # Декодируем имя и специализацию если они в байтах
            name = row[1]
            if isinstance(name, bytes):
                name = name.decode('utf-8')
            
            specialization = row[2]
            if isinstance(specialization, bytes):
                specialization = specialization.decode('utf-8')
            
            masters.append({
                'id': row[0],
                'name': name,
                'specialization': specialization
            })
        
        print(f"👥 Найдено мастеров: {len(masters)}")
        for master in masters:
            print(f"   - {master['name']} (ID: {master['id']}, {master['specialization']})")
        
        return masters
    
    def get_master_services(self, master_id: int) -> List[int]:
        """Получает услуги, которые может выполнять конкретный мастер"""
        query = f"SELECT service_id FROM master_services WHERE master_id = {master_id}"
        result = execute_query(query)
        
        service_ids = [row[0] for row in result]
        return service_ids
    
    def clear_weekly_data(self):
        """Очищает данные на неделю"""
        print("🗄️ Очистка данных на неделю...")
        
        try:
            # Получаем ID записей для удаления
            appointments_query = f"""
                SELECT id FROM appointments 
                WHERE CAST(start_time AS Date) >= CAST('{self.start_date}' AS Date) 
                AND CAST(start_time AS Date) <= CAST('{self.end_date}' AS Date)
            """
            appointment_ids = execute_query(appointments_query)
            
            # Удаляем записи по одной
            for row in appointment_ids:
                delete_record("appointments", f"id = {row[0]}")
            
            print(f"✅ Удалено записей: {len(appointment_ids)}")
            
            # Получаем ID графиков работы для удаления
            schedules_query = f"""
                SELECT id FROM master_schedules 
                WHERE CAST(date AS Date) >= CAST('{self.start_date}' AS Date) 
                AND CAST(date AS Date) <= CAST('{self.end_date}' AS Date)
            """
            schedule_ids = execute_query(schedules_query)
            
            # Удаляем графики по одному
            for row in schedule_ids:
                delete_record("master_schedules", f"id = {row[0]}")
            
            print(f"✅ Удалено графиков работы: {len(schedule_ids)}")
            
        except Exception as e:
            print(f"❌ Ошибка при очистке: {e}")
            raise
    
    def create_master_schedules(self, masters: List[Dict]):
        """Создает графики работы мастеров на неделю"""
        print("📅 Создание графиков работы мастеров на неделю...")
        
        try:
            # Получаем максимальный ID
            max_id_query = "SELECT MAX(id) as max_id FROM master_schedules"
            max_id_result = execute_query(max_id_query)
            max_id = max_id_result[0][0] if max_id_result[0][0] is not None else 0
            
            current_date = self.start_date
            schedule_id = max_id + 1
            
            while current_date <= self.end_date:
                for master in masters:
                    schedule_data = {
                        'id': schedule_id,
                        'master_id': master['id'],
                        'date': current_date,
                        'start_time': time(10, 0),  # 10:00
                        'end_time': time(18, 0)     # 18:00
                    }
                    
                    upsert_record('master_schedules', schedule_data)
                    schedule_id += 1
                
                current_date += timedelta(days=1)
            
            print("✅ Графики работы созданы")
            
        except Exception as e:
            print(f"❌ Ошибка при создании графиков: {e}")
            raise
    
    def generate_time_patterns(self, services: List[Dict], masters: List[Dict]) -> Dict[Tuple[int, date], List[Tuple[time, time]]]:
        """Генерирует паттерны времени для каждой услуги на каждый день"""
        print("⏰ Генерация паттернов времени...")
        
        patterns = {}
        
        # Базовые временные интервалы
        base_intervals = [
            (time(10, 0), time(13, 0)),  # 3 часа
            (time(13, 0), time(16, 0)),  # 3 часа  
            (time(16, 0), time(18, 0)),  # 2 часа
        ]
        
        # Дополнительные интервалы для разнообразия
        extended_intervals = [
            (time(10, 0), time(14, 0)),  # 4 часа
            (time(14, 0), time(18, 0)),  # 4 часа
            (time(10, 0), time(12, 0)),  # 2 часа
            (time(12, 0), time(15, 0)),  # 3 часа
            (time(15, 0), time(18, 0)),  # 3 часа
        ]
        
        current_date = self.start_date
        
        while current_date <= self.end_date:
            for service in services:
                # Случайно выбираем паттерн для этой услуги на этот день
                if random.random() < 0.3:  # 30% шанс на свободный слот
                    # Создаем свободный слот (3 часа)
                    free_start_hour = random.randint(10, 15)  # Свободный слот может быть с 10 до 15
                    free_start = time(free_start_hour, 0)
                    free_end = time(free_start_hour + 3, 0)
                    
                    # Создаем занятые интервалы вокруг свободного слота
                    intervals = []
                    
                    if free_start_hour > 10:
                        intervals.append((time(10, 0), free_start))
                    
                    if free_start_hour + 3 < 18:
                        intervals.append((free_end, time(18, 0)))
                    
                    patterns[(service['id'], current_date)] = intervals
                else:
                    # Обычный паттерн - мастер занят весь день
                    if random.random() < 0.5:
                        intervals = random.choice(base_intervals)
                        patterns[(service['id'], current_date)] = [intervals]
                    else:
                        intervals = random.choice(extended_intervals)
                        patterns[(service['id'], current_date)] = [intervals]
            
            current_date += timedelta(days=1)
        
        print("✅ Паттерны времени сгенерированы")
        return patterns
    
    def create_appointments(self, services: List[Dict], masters: List[Dict], patterns: Dict[Tuple[int, date], List[Tuple[time, time]]]):
        """Создает записи на основе сгенерированных паттернов"""
        print("📝 Создание записей...")
        
        try:
            # Получаем максимальный ID
            max_id_query = "SELECT MAX(id) as max_id FROM appointments"
            max_id_result = execute_query(max_id_query)
            max_id = max_id_result[0][0] if max_id_result[0][0] is not None else 0
            
            appointment_id = max_id + 1
            appointments_created = 0
            
            current_date = self.start_date
            
            while current_date <= self.end_date:
                for service in services:
                    # Получаем паттерн для этой услуги на этот день
                    pattern_key = (service['id'], current_date)
                    if pattern_key not in patterns:
                        continue
                    
                    intervals = patterns[pattern_key]
                    
                    # Находим мастеров, которые могут выполнять эту услугу
                    available_masters = []
                    for master in masters:
                        master_services = self.get_master_services(master['id'])
                        if service['id'] in master_services:
                            available_masters.append(master)
                    
                    if not available_masters:
                        continue
                    
                    # Случайно выбираем мастера для этой услуги
                    selected_master = random.choice(available_masters)
                    
                    # Создаем записи для каждого интервала
                    for start_time, end_time in intervals:
                        appointment_data = {
                            'id': appointment_id,
                            'user_telegram_id': self.fake_user_telegram_id,
                            'master_id': selected_master['id'],
                            'service_id': service['id'],
                            'start_time': datetime.combine(current_date, start_time),
                            'end_time': datetime.combine(current_date, end_time)
                        }
                        
                        upsert_record('appointments', appointment_data)
                        appointments_created += 1
                        
                        print(f"✅ Запись {appointments_created}: {service['name']} - "
                              f"Мастер {selected_master['name']} - "
                              f"{current_date} {start_time.strftime('%H:%M')}-{end_time.strftime('%H:%M')}")
                        
                        appointment_id += 1
                
                current_date += timedelta(days=1)
            
            print(f"✅ Создано записей: {appointments_created}")
            
        except Exception as e:
            print(f"❌ Ошибка при создании записей: {e}")
            raise
    
    def verify_generated_data(self):
        """Проверяет сгенерированные данные"""
        print("\n🔍 Проверка сгенерированных данных...")
        
        try:
            # Проверяем количество записей на неделю
            appointments_query = f"""
                SELECT COUNT(*) FROM appointments 
                WHERE CAST(start_time AS Date) >= CAST('{self.start_date}' AS Date) 
                AND CAST(start_time AS Date) <= CAST('{self.end_date}' AS Date)
            """
            appointments_count = execute_query(appointments_query)[0][0]
            print(f"📝 Записей создано: {appointments_count}")
            
            # Проверяем количество графиков работы
            schedules_query = f"""
                SELECT COUNT(*) FROM master_schedules 
                WHERE CAST(date AS Date) >= CAST('{self.start_date}' AS Date) 
                AND CAST(date AS Date) <= CAST('{self.end_date}' AS Date)
            """
            schedules_count = execute_query(schedules_query)[0][0]
            print(f"📅 Графиков работы создано: {schedules_count}")
            
            # Показываем статистику по дням
            print("\n📊 Статистика по дням:")
            current_date = self.start_date
            while current_date <= self.end_date:
                day_appointments_query = f"""
                    SELECT COUNT(*) FROM appointments 
                    WHERE CAST(start_time AS Date) = CAST('{current_date}' AS Date)
                """
                day_count = execute_query(day_appointments_query)[0][0]
                print(f"   {current_date.strftime('%Y-%m-%d (%A)')}: {day_count} записей")
                current_date += timedelta(days=1)
            
        except Exception as e:
            print(f"❌ Ошибка при проверке данных: {e}")
            raise
    
    def generate_weekly_schedule(self):
        """Основной метод генерации расписания на неделю"""
        print("🚀 Запуск генератора расписания на неделю")
        print(f"📅 Период: {self.start_date} - {self.end_date}")
        print("-" * 60)
        
        try:
            # Получаем данные из БД
            services = self.get_all_services()
            masters = self.get_all_masters()
            
            if not services:
                print("❌ Не найдено услуг в базе данных")
                return 1
            
            if not masters:
                print("❌ Не найдено мастеров в базе данных")
                return 1
            
            # Очищаем старые данные
            self.clear_weekly_data()
            
            # Создаем графики работы
            self.create_master_schedules(masters)
            
            # Генерируем паттерны времени
            patterns = self.generate_time_patterns(services, masters)
            
            # Создаем записи
            self.create_appointments(services, masters, patterns)
            
            # Проверяем результат
            self.verify_generated_data()
            
            print("\n" + "=" * 60)
            print("🎉 РАСПИСАНИЕ НА НЕДЕЛЮ СОЗДАНО!")
            print("=" * 60)
            print(f"📅 Период: {self.start_date} - {self.end_date}")
            print(f"📋 Услуг: {len(services)}")
            print(f"👥 Мастеров: {len(masters)}")
            print("\n✨ Особенности сгенерированного расписания:")
            print("   • Каждый мастер занят одной услугой с 10:00 до 18:00")
            print("   • У каждой услуги на каждый день разное время")
            print("   • Иногда есть свободные слоты по 3 часа")
            print("   • Реалистичное распределение нагрузки")
            print("=" * 60)
            
            return 0
            
        except Exception as e:
            print(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
            return 1


def main():
    """Основная функция"""
    generator = WeeklyScheduleGenerator()
    
    try:
        # Инициализируем подключение к БД
        init_database()
        
        # Генерируем расписание
        exit_code = generator.generate_weekly_schedule()
        
        return exit_code
        
    except Exception as e:
        print(f"\n❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        return 1
    
    finally:
        # Закрываем соединение с БД
        close_database()


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
