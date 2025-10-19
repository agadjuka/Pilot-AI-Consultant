#!/usr/bin/env python3
"""
Скрипт для выполнения миграций YDB через чистый YDB драйвер
Обходит проблемы с SQLAlchemy + YDB
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

def run_migrations_with_ydb():
    """Выполняет миграции через чистый YDB драйвер"""
    try:
        logger.info("🚀 Запускаем миграции YDB через чистый драйвер...")
        
        # Получаем настройки
        from app.core.config import settings
        
        endpoint = settings.YDB_ENDPOINT
        database = settings.YDB_DATABASE
        service_account_key_file = os.getenv("YC_SERVICE_ACCOUNT_KEY_FILE", "key.json")
        
        logger.info(f"Подключаемся к эндпоинту: {endpoint}")
        logger.info(f"База данных: {database}")
        
        # Проверяем существование файла ключа
        key_file_path = service_account_key_file
        if not os.path.exists(key_file_path):
            key_file_path = os.path.join(project_root, service_account_key_file)
        
        if not os.path.exists(key_file_path):
            logger.error(f"❌ Ошибка: Файл ключа {service_account_key_file} не найден.")
            return
        
        logger.info(f"Найден файл ключа: {os.path.abspath(key_file_path)}")
        
        # Создаем драйвер
        driver_config = ydb.DriverConfig(
            endpoint=endpoint,
            database=database,
            credentials=ydb.iam.ServiceAccountCredentials.from_file(key_file_path),
        )
        
        with ydb.Driver(driver_config) as driver:
            driver.wait(timeout=5, fail_fast=True)
            logger.info("✅ Подключение к YDB установлено")
            
            # Создаем таблицы через YQL
            with ydb.SessionPool(driver) as pool:
                
                def create_tables(session):
                    # Создание таблицы services
                    session.execute_scheme("""
                        CREATE TABLE IF NOT EXISTS services (
                            id Int32,
                            name String,
                            description Text,
                            price Double,
                            duration_minutes Int32,
                            PRIMARY KEY (id)
                        )
                    """)
                    
                    # Создание таблицы masters
                    session.execute_scheme("""
                        CREATE TABLE IF NOT EXISTS masters (
                            id Int32,
                            name String,
                            specialization String,
                            PRIMARY KEY (id)
                        )
                    """)
                    
                    # Создание ассоциативной таблицы master_services
                    session.execute_scheme("""
                        CREATE TABLE IF NOT EXISTS master_services (
                            master_id Int32,
                            service_id Int32,
                            PRIMARY KEY (master_id, service_id)
                        )
                    """)
                    
                    # Создание таблицы clients
                    session.execute_scheme("""
                        CREATE TABLE IF NOT EXISTS clients (
                            id Int32,
                            telegram_id Int64,
                            first_name String,
                            phone_number String,
                            PRIMARY KEY (id)
                        )
                    """)
                    
                    # Создание таблицы appointments
                    session.execute_scheme("""
                        CREATE TABLE IF NOT EXISTS appointments (
                            id Int32,
                            user_telegram_id Int64,
                            master_id Int32,
                            service_id Int32,
                            start_time Timestamp,
                            end_time Timestamp,
                            PRIMARY KEY (id)
                        )
                    """)
                    
                    # Создание таблицы dialog_history
                    session.execute_scheme("""
                        CREATE TABLE IF NOT EXISTS dialog_history (
                            id Int32,
                            user_id Int64,
                            role String,
                            message_text Text,
                            timestamp Timestamp,
                            PRIMARY KEY (id)
                        )
                    """)
                
                # Выполняем создание таблиц
                pool.retry_operation_sync(create_tables)
                logger.info("✅ Все таблицы успешно созданы!")
                
    except Exception as e:
        logger.error(f"❌ Ошибка выполнения миграций: {e}")
        raise

if __name__ == "__main__":
    run_migrations_with_ydb()
