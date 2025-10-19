#!/usr/bin/env python3
"""
Тест с явным коммитом транзакции
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

def test_with_commit():
    """Тестирует добавление с явным коммитом"""
    
    logger.info("🧪 Тест с явным коммитом транзакции...")
    
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
                
                def insert_with_commit(session):
                    # Используем явный коммит транзакции
                    tx = session.transaction()
                    try:
                        query = """
                            UPSERT INTO services (id, name, description, price, duration_minutes)
                            VALUES (888, 'Тест с коммитом', 'Описание с коммитом', 2000.0, 90)
                        """
                        prepared = session.prepare(query)
                        tx.execute(prepared)
                        tx.commit()
                        logger.info("✅ Запись добавлена и закоммичена!")
                    except Exception as e:
                        tx.rollback()
                        logger.error(f"❌ Ошибка, откат транзакции: {e}")
                        raise
                
                pool.retry_operation_sync(insert_with_commit)
                
                # Проверяем результат
                def check_result(session):
                    prepared = session.prepare("SELECT COUNT(*) as count FROM services")
                    result = session.transaction().execute(prepared)
                    count = result[0].rows[0][0]
                    logger.info(f"📊 Количество записей в services: {count}")
                    
                    if count > 0:
                        prepared = session.prepare("SELECT * FROM services WHERE id = 888")
                        result = session.transaction().execute(prepared)
                        rows = result[0].rows
                        if rows:
                            logger.info(f"✅ Найдена запись: {list(rows[0])}")
                        else:
                            logger.warning("⚠️ Запись не найдена")
                
                pool.retry_operation_sync(check_result)
                
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        raise

if __name__ == "__main__":
    test_with_commit()
