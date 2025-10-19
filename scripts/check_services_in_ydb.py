#!/usr/bin/env python3
"""
Проверка данных в YDB
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

def check_ydb_data():
    """Проверяет данные в YDB"""
    
    logger.info("🔍 Проверяем данные в YDB...")
    
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
                
                def check_services(session):
                    try:
                        # Проверяем количество записей
                        prepared = session.prepare("SELECT COUNT(*) as count FROM services")
                        result = session.transaction().execute(prepared)
                        count = result[0].rows[0][0]
                        logger.info(f"📊 Таблица services: {count} записей")
                        
                        if count > 0:
                            # Показываем все записи
                            prepared = session.prepare("SELECT * FROM services ORDER BY id")
                            result = session.transaction().execute(prepared)
                            rows = result[0].rows
                            logger.info(f"   Все услуги:")
                            for row in rows:
                                logger.info(f"   ID: {row[0]}, Название: {row[1]}, Цена: {row[3]}")
                                    
                    except Exception as e:
                        logger.warning(f"⚠️ Не удалось проверить таблицу services: {e}")
                
                pool.retry_operation_sync(check_services)
                
    except Exception as e:
        logger.error(f"❌ Ошибка проверки данных: {e}")
        raise

if __name__ == "__main__":
    check_ydb_data()
