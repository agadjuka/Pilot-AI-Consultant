#!/usr/bin/env python3
"""
Тест добавления ОДНОЙ записи в YDB
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

def test_single_insert():
    """Тестирует добавление ОДНОЙ записи"""
    
    logger.info("🧪 Тест добавления ОДНОЙ записи в services...")
    
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
                
                def insert_one_service(session):
                    # Добавляем ОДНУ запись
                    query = """
                        UPSERT INTO services (id, name, description, price, duration_minutes)
                        VALUES (999, 'Тестовая услуга', 'Описание тестовой услуги', 1000.0, 60)
                    """
                    prepared = session.prepare(query)
                    session.transaction().execute(prepared)
                    logger.info("✅ Добавлена тестовая услуга!")
                
                pool.retry_operation_sync(insert_one_service)
                
                # Проверяем, что запись добавилась
                def check_insert(session):
                    prepared = session.prepare("SELECT COUNT(*) as count FROM services")
                    result = session.transaction().execute(prepared)
                    count = result[0].rows[0][0]
                    logger.info(f"📊 Количество записей в services: {count}")
                    
                    if count > 0:
                        prepared = session.prepare("SELECT * FROM services WHERE id = 999")
                        result = session.transaction().execute(prepared)
                        rows = result[0].rows
                        if rows:
                            logger.info(f"✅ Найдена тестовая запись: {list(rows[0])}")
                        else:
                            logger.warning("⚠️ Тестовая запись не найдена")
                
                pool.retry_operation_sync(check_insert)
                
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        raise

if __name__ == "__main__":
    test_single_insert()
