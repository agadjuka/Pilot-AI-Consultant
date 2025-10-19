"""
Скрипт для создания таблицы master_schedules и удаления старых таблиц в YDB
"""

import ydb
import os
import logging
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Загружаем переменные окружения
load_dotenv()


def update_schedule_tables():
    """
    Создает новую таблицу master_schedules и удаляет старые таблицы
    """
    
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
            
            def create_master_schedules_table(session):
                """Создает таблицу master_schedules"""
                query = """
                CREATE TABLE master_schedules (
                    id Int32,
                    master_id Int32,
                    date Date,
                    start_time String,
                    end_time String,
                    PRIMARY KEY (id)
                )
                """
                session.execute_scheme(query)
                logger.info("✅ Таблица master_schedules создана")
            
            def drop_old_tables(session):
                """Удаляет старые таблицы"""
                try:
                    # Удаляем work_schedules
                    query = "DROP TABLE work_schedules"
                    session.execute_scheme(query)
                    logger.info("✅ Таблица work_schedules удалена")
                except Exception as e:
                    if "not found" in str(e).lower():
                        logger.info("ℹ️ Таблица work_schedules не найдена (уже удалена)")
                    else:
                        logger.warning(f"⚠️ Ошибка удаления work_schedules: {e}")
                
                try:
                    # Удаляем schedule_exceptions
                    query = "DROP TABLE schedule_exceptions"
                    session.execute_scheme(query)
                    logger.info("✅ Таблица schedule_exceptions удалена")
                except Exception as e:
                    if "not found" in str(e).lower():
                        logger.info("ℹ️ Таблица schedule_exceptions не найдена (уже удалена)")
                    else:
                        logger.warning(f"⚠️ Ошибка удаления schedule_exceptions: {e}")
            
            try:
                # Сначала создаем новую таблицу
                pool.retry_operation_sync(create_master_schedules_table)
                
                # Затем удаляем старые таблицы
                pool.retry_operation_sync(drop_old_tables)
                
                logger.info("🎉 Миграция таблиц успешно завершена!")
                
            except Exception as e:
                if "already exists" in str(e).lower():
                    logger.warning("⚠️ Таблица master_schedules уже существует")
                else:
                    logger.error(f"❌ Ошибка миграции таблиц: {e}")
                    raise


if __name__ == "__main__":
    try:
        update_schedule_tables()
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        exit(1)
