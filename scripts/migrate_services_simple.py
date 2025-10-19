#!/usr/bin/env python3
"""
Простой перенос таблицы services одним запросом
"""

import os
import sys
import sqlite3
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

def migrate_services_simple():
    """Переносит таблицу services одним запросом"""
    
    logger.info("🚀 Переносим таблицу services одним запросом...")
    
    # Подключаемся к SQLite
    sqlite_conn = sqlite3.connect("beauty_salon.db")
    sqlite_cursor = sqlite_conn.cursor()
    
    try:
        # Получаем данные services из SQLite
        sqlite_cursor.execute("SELECT id, name, description, price, duration_minutes FROM services")
        services_data = sqlite_cursor.fetchall()
        
        logger.info(f"📋 Найдено {len(services_data)} услуг в SQLite")
        
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
                
                def insert_all_services(session):
                    # Создаем один большой INSERT запрос
                    values = []
                    for service in services_data:
                        name = service[1].replace("'", "''")
                        desc = service[2].replace("'", "''") if service[2] else ""
                        values.append(f"({service[0]}, '{name}', '{desc}', {service[3]}, {service[4]})")
                    
                    query = f"""
                        INSERT INTO services (id, name, description, price, duration_minutes)
                        VALUES {', '.join(values)}
                    """
                    
                    logger.info(f"📝 Выполняем запрос с {len(values)} значениями...")
                    prepared = session.prepare(query)
                    session.transaction().execute(prepared)
                    logger.info("✅ Все услуги добавлены!")
                
                pool.retry_operation_sync(insert_all_services)
                logger.info(f"🎉 Успешно перенесено {len(services_data)} услуг!")
                
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        raise
    finally:
        sqlite_conn.close()

if __name__ == "__main__":
    migrate_services_simple()
