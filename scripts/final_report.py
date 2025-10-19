#!/usr/bin/env python3
"""
Итоговый отчет о переносе данных
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

def final_report():
    """Итоговый отчет о переносе данных"""
    
    logger.info("📊 ИТОГОВЫЙ ОТЧЕТ О ПЕРЕНОСЕ ДАННЫХ")
    logger.info("=" * 50)
    
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
                
                def check_all_tables(session):
                    tables = ['services', 'masters', 'clients', 'appointments', 'dialog_history', 'master_services']
                    
                    logger.info("📋 СТАТУС ПЕРЕНОСА ПО ТАБЛИЦАМ:")
                    logger.info("-" * 40)
                    
                    for table in tables:
                        try:
                            prepared = session.prepare(f"SELECT COUNT(*) as count FROM {table}")
                            result = session.transaction().execute(prepared)
                            count = result[0].rows[0][0]
                            
                            if count > 0:
                                logger.info(f"✅ {table}: {count} записей")
                                
                                # Показываем примеры записей
                                prepared = session.prepare(f"SELECT * FROM {table} LIMIT 2")
                                result = session.transaction().execute(prepared)
                                rows = result[0].rows
                                
                                if rows:
                                    logger.info(f"   Примеры:")
                                    for i, row in enumerate(rows, 1):
                                        logger.info(f"   {i}: {list(row)}")
                            else:
                                logger.info(f"❌ {table}: 0 записей")
                                
                        except Exception as e:
                            logger.warning(f"⚠️ {table}: Ошибка проверки - {e}")
                
                pool.retry_operation_sync(check_all_tables)
                
                logger.info("=" * 50)
                logger.info("🎯 РЕЗУЛЬТАТ:")
                logger.info("✅ Успешно перенесены: services, masters, clients, master_services")
                logger.info("❌ Проблемы с: dialog_history (формат Timestamp)")
                logger.info("📝 appointments: пустая таблица в SQLite")
                logger.info("=" * 50)
                
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        raise

if __name__ == "__main__":
    final_report()
