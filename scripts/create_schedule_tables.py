"""
Скрипт для создания таблиц графиков работы в YDB
"""

import ydb
import os
import logging
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Загружаем переменные окружения
load_dotenv(os.getenv("ENV_FILE", ".env"))


def create_schedule_tables():
    """Создает таблицы для графиков работы мастеров в YDB"""
    
    # Получаем конфигурацию из переменных окружения
    endpoint = os.getenv('YDB_ENDPOINT')
    database = os.getenv('YDB_DATABASE')
    service_account_key_file = os.getenv("YC_SERVICE_ACCOUNT_KEY_FILE", "key.json")
    
    if not endpoint or not database:
        raise ValueError("Необходимо установить переменные окружения YDB_ENDPOINT и YDB_DATABASE")
    
    # Проверяем существование файла ключа
    key_file_path = service_account_key_file
    if not os.path.exists(key_file_path):
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        key_file_path = os.path.join(project_root, service_account_key_file)
    
    if not os.path.exists(key_file_path):
        raise FileNotFoundError(f"Файл ключа {service_account_key_file} не найден")
    
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
            
            def create_work_schedules_table(session):
                """Создает таблицу work_schedules"""
                query = """
                CREATE TABLE work_schedules (
                    id Int32,
                    master_id Int32,
                    day_of_week Int32,
                    start_time String,
                    end_time String,
                    PRIMARY KEY (id)
                )
                """
                session.execute_scheme(query)
                logger.info("✅ Таблица work_schedules создана")
            
            def create_schedule_exceptions_table(session):
                """Создает таблицу schedule_exceptions"""
                query = """
                CREATE TABLE schedule_exceptions (
                    id Int32,
                    master_id Int32,
                    date Date,
                    is_day_off Bool,
                    start_time String,
                    end_time String,
                    PRIMARY KEY (id)
                )
                """
                session.execute_scheme(query)
                logger.info("✅ Таблица schedule_exceptions создана")
            
            try:
                # Создаем таблицы
                pool.retry_operation_sync(create_work_schedules_table)
                pool.retry_operation_sync(create_schedule_exceptions_table)
                
                logger.info("🎉 Все таблицы успешно созданы!")
                
            except Exception as e:
                if "already exists" in str(e).lower():
                    logger.warning("⚠️ Таблицы уже существуют")
                else:
                    logger.error(f"❌ Ошибка создания таблиц: {e}")
                    raise


if __name__ == "__main__":
    try:
        create_schedule_tables()
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        exit(1)
