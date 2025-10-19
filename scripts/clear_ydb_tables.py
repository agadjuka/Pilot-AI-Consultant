#!/usr/bin/env python3
"""
Очистка таблиц YDB перед переносом данных
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

def clear_ydb_tables():
    """Очищает все таблицы в YDB"""
    
    logger.info("🧹 Очищаем таблицы YDB...")
    
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
        
        if not os.path.exists(key_file_path):
            logger.error(f"❌ Файл ключа {service_account_key_file} не найден")
            return
        
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
                
                def clear_tables(session):
                    # Очищаем таблицы в правильном порядке (с учетом внешних ключей)
                    tables_to_clear = [
                        'dialog_history',
                        'appointments', 
                        'master_services',
                        'clients',
                        'masters',
                        'services'
                    ]
                    
                    for table in tables_to_clear:
                        try:
                            # В YDB используется execute_query для DELETE
                            session.execute_query(f"DELETE FROM {table}")
                            logger.info(f"✅ Очищена таблица {table}")
                        except Exception as e:
                            logger.warning(f"⚠️ Не удалось очистить таблицу {table}: {e}")
                
                pool.retry_operation_sync(clear_tables)
                logger.info("🎉 Очистка таблиц завершена!")
                
    except Exception as e:
        logger.error(f"❌ Ошибка очистки таблиц: {e}")
        raise

if __name__ == "__main__":
    clear_ydb_tables()
