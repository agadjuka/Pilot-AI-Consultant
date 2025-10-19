#!/usr/bin/env python3
"""
Простой тест YDB запросов
"""

import os
import sys
from dotenv import load_dotenv

# Добавляем корень проекта в путь
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Загружаем переменные окружения
load_dotenv()

import ydb
import logging

# Настраиваем логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_ydb_queries():
    """Тестирует различные способы выполнения запросов в YDB"""
    
    logger.info("🧪 Тестируем YDB запросы...")
    
    try:
        # Подключаемся к YDB
        from app.core.config import settings
        
        endpoint = settings.YDB_ENDPOINT
        database = settings.YDB_DATABASE
        service_account_key_file = os.getenv("YC_SERVICE_ACCOUNT_KEY_FILE", "key.json")
        
        # Проверяем файл ключа
        key_file_path = service_account_key_file
        if not os.path.exists(key_file_path):
            key_file_path = os.path.join(project_root, service_account_key_file)
        
        # Создаем драйвер YDB
        driver_config = ydb.DriverConfig(
            endpoint=endpoint,
            database=database,
            credentials=ydb.iam.ServiceAccountCredentials.from_file(key_file_path),
        )
        
        with ydb.Driver(driver_config) as driver:
            driver.wait(timeout=5, fail_fast=True)
            logger.info("✅ Подключение к YDB установлено")
            
            with ydb.SessionPool(driver) as pool:
                
                def test_query_methods(session):
                    # Сначала посмотрим, какие методы доступны у session
                    logger.info("🔍 Доступные методы session:")
                    methods = [method for method in dir(session) if not method.startswith('_')]
                    logger.info(f"Методы: {methods}")
                    
                    try:
                        # Попробуем execute_query
                        logger.info("🔍 Пробуем execute_query")
                        result = session.execute_query("SELECT COUNT(*) as count FROM services")
                        count = result[0].rows[0][0]
                        logger.info(f"✅ Результат: {count} записей в services")
                        
                    except Exception as e:
                        logger.error(f"❌ execute_query не работает: {e}")
                    
                    try:
                        # Попробуем execute
                        logger.info("🔍 Пробуем execute")
                        result = session.execute("SELECT COUNT(*) as count FROM services")
                        count = result[0].rows[0][0]
                        logger.info(f"✅ Результат: {count} записей в services")
                        
                    except Exception as e:
                        logger.error(f"❌ execute не работает: {e}")
                    
                    try:
                        # Попробуем через транзакцию
                        logger.info("🔍 Пробуем через транзакцию")
                        def query_func():
                            return session.execute_query("SELECT COUNT(*) as count FROM services")
                        
                        result = session.transaction().execute(query_func)
                        count = result[0].rows[0][0]
                        logger.info(f"✅ Результат: {count} записей в services")
                        
                    except Exception as e:
                        logger.error(f"❌ Транзакция не работает: {e}")
                    
                    try:
                        # Попробуем через prepare
                        logger.info("🔍 Пробуем через prepare")
                        prepared = session.prepare("SELECT COUNT(*) as count FROM services")
                        result = session.transaction().execute(prepared)
                        count = result[0].rows[0][0]
                        logger.info(f"✅ Результат: {count} записей в services")
                        
                    except Exception as e:
                        logger.error(f"❌ Prepare не работает: {e}")
                
                pool.retry_operation_sync(test_query_methods)
                
    except Exception as e:
        logger.error(f"❌ Ошибка тестирования: {e}")
        raise

if __name__ == "__main__":
    test_ydb_queries()
