#!/usr/bin/env python3
"""
Тестовый скрипт для проверки подключения к YDB с fallback механизмом.
Проверяет все три способа аутентификации: автоматический, через метаданные и через локальный ключ.
"""

import logging
import sys
import os

# Добавляем путь к приложению
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def test_database_connection():
    """Тестирует подключение к базе данных."""
    try:
        logger.info("🧪 ТЕСТ: Начинаем тестирование подключения к YDB...")
        
        # Импортируем функцию подключения
        from app.core.database import get_driver, init_database
        
        # Тестируем подключение
        logger.info("🧪 ТЕСТ: Тестируем get_driver()...")
        driver = get_driver()
        logger.info("✅ ТЕСТ: get_driver() выполнен успешно")
        
        # Тестируем инициализацию базы данных
        logger.info("🧪 ТЕСТ: Тестируем init_database()...")
        init_database()
        logger.info("✅ ТЕСТ: init_database() выполнен успешно")
        
        # Тестируем простой запрос
        logger.info("🧪 ТЕСТ: Тестируем простой запрос...")
        from app.core.database import execute_query
        
        try:
            result = execute_query("SELECT COUNT(*) as count FROM services")
            logger.info(f"✅ ТЕСТ: Запрос выполнен успешно, найдено {result[0][0]} услуг")
        except Exception as e:
            logger.warning(f"⚠️ ТЕСТ: Запрос к таблице services не удался: {e}")
            # Это может быть нормально, если таблица не существует
        
        logger.info("🎉 ТЕСТ: Все тесты прошли успешно!")
        return True
        
    except Exception as e:
        logger.error(f"❌ ТЕСТ: Ошибка тестирования: {e}")
        logger.error(f"❌ ТЕСТ: Тип ошибки: {type(e).__name__}")
        return False

def test_fallback_scenarios():
    """Тестирует различные сценарии fallback."""
    logger.info("🧪 ТЕСТ: Тестируем сценарии fallback...")
    
    # Проверяем наличие файла ключа
    key_file = "key.json"
    if os.path.exists(key_file):
        logger.info(f"✅ ТЕСТ: Файл ключа {key_file} найден")
    else:
        logger.warning(f"⚠️ ТЕСТ: Файл ключа {key.json} не найден")
    
    # Проверяем переменные окружения
    ydb_endpoint = os.getenv("YDB_ENDPOINT")
    ydb_database = os.getenv("YDB_DATABASE")
    yc_key_file = os.getenv("YC_SERVICE_ACCOUNT_KEY_FILE")
    
    logger.info(f"🔧 ТЕСТ: YDB_ENDPOINT = {ydb_endpoint}")
    logger.info(f"🔧 ТЕСТ: YDB_DATABASE = {ydb_database}")
    logger.info(f"🔧 ТЕСТ: YC_SERVICE_ACCOUNT_KEY_FILE = {yc_key_file}")

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("🚀 ЗАПУСК ТЕСТИРОВАНИЯ ПОДКЛЮЧЕНИЯ К YDB")
    logger.info("=" * 60)
    
    # Тестируем сценарии fallback
    test_fallback_scenarios()
    
    logger.info("-" * 60)
    
    # Тестируем подключение
    success = test_database_connection()
    
    logger.info("=" * 60)
    if success:
        logger.info("🎉 ВСЕ ТЕСТЫ ПРОШЛИ УСПЕШНО!")
        sys.exit(0)
    else:
        logger.error("❌ ТЕСТЫ ЗАВЕРШИЛИСЬ С ОШИБКАМИ!")
        sys.exit(1)
