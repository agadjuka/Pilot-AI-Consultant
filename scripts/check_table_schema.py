#!/usr/bin/env python3
"""
Проверка схемы таблицы services в YDB
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

def check_table_schema():
    """Проверяет схему таблицы services"""
    
    logger.info("🔍 Проверяем схему таблицы services...")
    
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
                
                def check_schema(session):
                    try:
                        # Проверяем, существует ли таблица
                        logger.info("🔍 Проверяем существование таблицы services...")
                        result = session.describe_table("services")
                        logger.info("✅ Таблица services существует!")
                        logger.info(f"📋 Схема таблицы: {result}")
                        
                    except Exception as e:
                        logger.error(f"❌ Таблица services не существует или ошибка: {e}")
                        
                        # Попробуем создать таблицу
                        logger.info("🔨 Создаем таблицу services...")
                        try:
                            session.execute_scheme("""
                                CREATE TABLE services (
                                    id Int32,
                                    name String,
                                    description Text,
                                    price Double,
                                    duration_minutes Int32,
                                    PRIMARY KEY (id)
                                )
                            """)
                            logger.info("✅ Таблица services создана!")
                        except Exception as create_error:
                            logger.error(f"❌ Ошибка создания таблицы: {create_error}")
                
                pool.retry_operation_sync(check_schema)
                
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        raise

if __name__ == "__main__":
    check_table_schema()
