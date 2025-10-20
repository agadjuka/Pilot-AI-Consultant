"""
Скрипт для наполнения графиков работы мастеров в YDB
"""

import os
import sys
import logging
import time
import random
from datetime import time as dt_time, date
from dotenv import load_dotenv

# Добавляем корневую директорию проекта в путь
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import execute_query, upsert_record, delete_record

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Загружаем переменные окружения
load_dotenv(os.getenv("ENV_FILE", ".env"))


def cleanup_old_data():
    """Очищает старые данные графиков работы"""
    try:
        logger.info("🧹 Очищаем старые данные графиков работы...")
        
        # Очищаем таблицы графиков
        delete_record('work_schedules', '1=1')  # Удаляем все записи
        delete_record('schedule_exceptions', '1=1')  # Удаляем все записи
        
        logger.info("✅ Старые данные очищены")
        
    except Exception as e:
        logger.error(f"❌ Ошибка очистки данных: {e}")
        raise


def get_random_schedule():
    """Генерирует случайный график работы в диапазоне 10:00-20:00"""
    # Базовое время начала (10:00-11:00)
    start_hour = random.randint(10, 11)
    start_minute = random.choice([0, 30])
    
    # Базовое время окончания (18:00-20:00)
    end_hour = random.randint(18, 20)
    end_minute = random.choice([0, 30])
    
    # Иногда делаем более короткий день
    if random.random() < 0.3:  # 30% вероятность короткого дня
        end_hour = random.randint(16, 18)
    
    start_time = f"{start_hour:02d}:{start_minute:02d}:00"
    end_time = f"{end_hour:02d}:{end_minute:02d}:00"
    
    return start_time, end_time


def seed_work_schedules():
    """Наполняет таблицы графиков работы тестовыми данными"""
    
    try:
        logger.info("🗄️ Начинаем наполнение графиков работы...")
        
        # Очищаем старые данные
        cleanup_old_data()
        
        # Получаем всех мастеров
        masters_query = "SELECT id FROM masters ORDER BY id"
        masters_rows = execute_query(masters_query)
        
        if not masters_rows:
            logger.warning("⚠️ Мастера не найдены. Сначала запустите основной seed.py")
            return
        
        masters = [row[0] for row in masters_rows]
        logger.info(f"📋 Найдено {len(masters)} мастеров")
        
        # Создаем графики работы для всех мастеров
        schedules_created = 0
        
        for master_id in masters:
            logger.info(f"📅 Создаем график для мастера {master_id}")
            
            # Генерируем случайный график для этого мастера
            start_time, end_time = get_random_schedule()
            logger.info(f"🕐 График мастера {master_id}: {start_time} - {end_time}")
            
            # Все мастера работают 5/2 с понедельника по пятницу
            for day in range(5):  # Пн-Пт (0-4)
                # Получаем следующий ID
                id_query = "SELECT MAX(id) as max_id FROM work_schedules"
                id_rows = execute_query(id_query)
                max_id = id_rows[0][0] if id_rows[0][0] is not None else 0
                new_id = max_id + 1
                
                # Создаем график работы
                schedule_data = {
                    'id': new_id,
                    'master_id': master_id,
                    'day_of_week': day,
                    'start_time': start_time,
                    'end_time': end_time
                }
                
                try:
                    upsert_record('work_schedules', schedule_data)
                    schedules_created += 1
                    logger.info(f"✅ Создан график для мастера {master_id}, день {day}")
                except Exception as e:
                    logger.error(f"❌ Ошибка создания графика для мастера {master_id}, день {day}: {e}")
                    continue
        
        logger.info(f"✅ Создано {schedules_created} записей графиков работы")
        
        # Создаем несколько примеров исключений для разных мастеров
        exceptions_created = 0
        
        # Выбираем несколько мастеров для создания исключений
        masters_for_exceptions = masters[:3]  # Первые 3 мастера
        
        for master_id in masters_for_exceptions:
            logger.info(f"📅 Создаем исключения для мастера {master_id}")
            
            # Примеры исключений
            exceptions = [
                {
                    'date': date(2024, 12, 31),  # Новый год - сокращенный день
                    'is_day_off': False,
                    'start_time': '10:00:00',
                    'end_time': '15:00:00'
                },
                {
                    'date': date(2025, 1, 1),  # Новый год - выходной
                    'is_day_off': True,
                    'start_time': None,
                    'end_time': None
                }
            ]
            
            for exception in exceptions:
                # Получаем следующий ID
                id_query = "SELECT MAX(id) as max_id FROM schedule_exceptions"
                id_rows = execute_query(id_query)
                max_id = id_rows[0][0] if id_rows[0][0] is not None else 0
                new_id = max_id + 1
                
                # Создаем исключение
                exception_data = {
                    'id': new_id,
                    'master_id': master_id,
                    'date': exception['date'],
                    'is_day_off': exception['is_day_off'],
                    'start_time': exception['start_time'],
                    'end_time': exception['end_time']
                }
                
                try:
                    upsert_record('schedule_exceptions', exception_data)
                    exceptions_created += 1
                    logger.info(f"✅ Создано исключение для мастера {master_id} на {exception['date']}")
                except Exception as e:
                    logger.error(f"❌ Ошибка создания исключения для мастера {master_id}: {e}")
                    continue
        
        logger.info(f"✅ Создано {exceptions_created} исключений из графика")
        logger.info("🎉 Графики работы успешно наполнены!")
        
    except Exception as e:
        logger.error(f"❌ Ошибка наполнения графиков: {e}")
        raise


if __name__ == "__main__":
    try:
        seed_work_schedules()
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        exit(1)