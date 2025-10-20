#!/usr/bin/env python3
"""
Тестовый скрипт для проверки исправления ошибки сравнения int с time.
"""

import os
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# Добавляем корневую папку проекта в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv(os.getenv("ENV_FILE", ".env"))

from app.core.logging_config import setup_logging
setup_logging()

from app.core.database import init_database
from app.repositories.schedule_repository import WorkScheduleRepository

def test_schedule_data():
    """Тестирует данные расписания, чтобы понять, что возвращается."""
    
    print("🧪 Тестирование данных расписания...")
    
    try:
        # Инициализируем базу данных
        init_database()
        print("✅ База данных инициализирована")
        
        # Создаем репозиторий
        schedule_repo = WorkScheduleRepository()
        print("✅ Репозиторий создан")
        
        # Тестируем получение расписания
        print("🔍 Тестируем получение расписания...")
        schedule = schedule_repo.find_by_master_and_day(9, 0)  # Понедельник
        
        if schedule:
            print(f"✅ Расписание найдено: {schedule}")
            print(f"📊 Тип start_time: {type(schedule['start_time'])}")
            print(f"📊 Тип end_time: {type(schedule['end_time'])}")
            print(f"📊 Значение start_time: {schedule['start_time']}")
            print(f"📊 Значение end_time: {schedule['end_time']}")
        else:
            print("⚠️ Расписание не найдено")
        
        print("\n🎉 Тест завершен!")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка во время тестирования: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_schedule_data()
    sys.exit(0 if success else 1)
