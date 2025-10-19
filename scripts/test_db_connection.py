#!/usr/bin/env python3
"""
Минимальный тест подключения к базе данных перед запуском основного скрипта
"""

import sys
sys.path.append('.')

def test_database_connection():
    """Тестирует подключение к базе данных"""
    try:
        print("Тестируем подключение к базе данных...")
        from app.core.database import execute_query
        
        # Простой тест - получаем количество мастеров
        result = execute_query("SELECT COUNT(*) FROM masters")
        masters_count = result[0][0] if result and result[0][0] is not None else 0
        print(f"✓ Подключение работает! Найдено мастеров: {masters_count}")
        
        # Тест получения услуг
        result = execute_query("SELECT COUNT(*) FROM services")
        services_count = result[0][0] if result and result[0][0] is not None else 0
        print(f"✓ Найдено услуг: {services_count}")
        
        # Тест получения графиков
        result = execute_query("SELECT COUNT(*) FROM master_schedules")
        schedules_count = result[0][0] if result and result[0][0] is not None else 0
        print(f"✓ Найдено графиков работы: {schedules_count}")
        
        return True
        
    except Exception as e:
        print(f"✗ Ошибка подключения к базе данных: {e}")
        return False

if __name__ == "__main__":
    if test_database_connection():
        print("\n✓ База данных доступна, можно запускать основной скрипт")
    else:
        print("\n✗ Проблемы с базой данных")
        sys.exit(1)
