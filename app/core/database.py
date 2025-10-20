"""
Модуль для работы с Yandex Database (YDB) через чистый драйвер
"""

import ydb
import os
import logging
from typing import Optional, Generator, Any, List, Dict
from contextlib import contextmanager
from dotenv import load_dotenv

# Получаем логгер для этого модуля
logger = logging.getLogger(__name__)

# Глобальные переменные для ленивой инициализации
_driver: Optional[ydb.Driver] = None
_session_pool: Optional[ydb.SessionPool] = None

# Загружаем переменные окружения
load_dotenv()


def get_driver() -> ydb.Driver:
    """Получить или создать драйвер YDB."""
    global _driver
    if _driver is None:
        from app.core.config import settings
        
        endpoint = settings.YDB_ENDPOINT
        database = settings.YDB_DATABASE
        
        logger.info(f"🔗 DATABASE: Подключение к YDB endpoint={endpoint}, database={database}")
        
        try:
            # Пробуем сначала без credentials (автоматическая аутентификация)
            logger.info("🔗 DATABASE: Пробуем автоматическую аутентификацию...")
            driver_config = ydb.DriverConfig(
                endpoint=endpoint,
                database=database,
                # Не указываем credentials - SDK сам получит IAM токен
            )
            
            _driver = ydb.Driver(driver_config)
            _driver.wait(timeout=10, fail_fast=True)
            logger.info("✅ DATABASE: Подключение к YDB установлено (автоматическая аутентификация)")
            
        except Exception as e1:
            logger.warning(f"⚠️ DATABASE: Автоматическая аутентификация не удалась: {e1}")
            
            try:
                # Fallback 1: пробуем с явными метаданными
                logger.info("🔗 DATABASE: Пробуем аутентификацию через метаданные...")
                driver_config = ydb.DriverConfig(
                    endpoint=endpoint,
                    database=database,
                    credentials=ydb.iam.MetadataUrlCredentials(),
                )
                
                _driver = ydb.Driver(driver_config)
                _driver.wait(timeout=10, fail_fast=True)
                logger.info("✅ DATABASE: Подключение к YDB установлено (через метаданные)")
                
            except Exception as e2:
                logger.warning(f"⚠️ DATABASE: Аутентификация через метаданные не удалась: {e2}")
                
                try:
                    # Fallback 2: пробуем с локальным файлом ключа
                    logger.info("🔗 DATABASE: Пробуем аутентификацию через локальный ключ...")
                    
                    # Получаем путь к файлу ключа из переменных окружения или используем по умолчанию
                    service_account_key_file = os.getenv("YC_SERVICE_ACCOUNT_KEY_FILE", "key.json")
                    
                    # Проверяем существование файла ключа
                    key_file_path = service_account_key_file
                    if not os.path.exists(key_file_path):
                        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                        key_file_path = os.path.join(project_root, service_account_key_file)
                    
                    if not os.path.exists(key_file_path):
                        raise FileNotFoundError(f"Файл ключа {service_account_key_file} не найден")
                    
                    logger.info(f"🔗 DATABASE: Используем файл ключа: {key_file_path}")
                    
                    driver_config = ydb.DriverConfig(
                        endpoint=endpoint,
                        database=database,
                        credentials=ydb.iam.ServiceAccountCredentials.from_file(key_file_path),
                    )
                    
                    _driver = ydb.Driver(driver_config)
                    _driver.wait(timeout=10, fail_fast=True)
                    logger.info("✅ DATABASE: Подключение к YDB установлено (через локальный ключ)")
                    
                except Exception as e3:
                    logger.error(f"❌ DATABASE: Все способы аутентификации не удались:")
                    logger.error(f"❌ DATABASE: 1. Автоматическая: {e1}")
                    logger.error(f"❌ DATABASE: 2. Метаданные: {e2}")
                    logger.error(f"❌ DATABASE: 3. Локальный ключ: {e3}")
                    raise Exception("Не удалось подключиться к YDB ни одним из способов аутентификации")
    
    return _driver




def get_session_pool() -> ydb.SessionPool:
    """Получить или создать пул сессий YDB."""
    global _session_pool
    if _session_pool is None:
        driver = get_driver()
        _session_pool = ydb.SessionPool(driver)
    return _session_pool


@contextmanager
def get_db_session():
    """
    Контекстный менеджер для получения сессии базы данных.
    Используется для автоматического управления сессиями.
    """
    pool = get_session_pool()
    
    def get_session():
        return pool.acquire()
    
    session = None
    try:
        session = pool.retry_operation_sync(get_session)
        yield session
    except Exception as e:
        logger.error(f"❌ DATABASE: Ошибка работы с сессией: {e}")
        raise
    finally:
        if session:
            pool.release(session)


def execute_query(query: str, params: Optional[Dict[str, Any]] = None) -> List[Any]:
    """
    Выполняет SELECT запрос и возвращает результат.
    
    Args:
        query: SQL запрос
        params: Параметры запроса (не используется в текущей реализации)
    
    Returns:
        Список строк результата
    """
    pool = get_session_pool()
    
    def execute(session):
        # Создаем новую транзакцию для каждой операции
        tx = session.transaction()
        try:
            prepared = session.prepare(query)
            result = tx.execute(prepared)
            tx.commit()
            logger.info(f"✅ DATABASE: SELECT выполнен успешно")
            return result[0].rows
        except Exception as e:
            # При ошибке откатываем транзакцию
            try:
                tx.rollback()
            except Exception as rollback_error:
                logger.warning(f"⚠️ DATABASE: Ошибка при откате транзакции: {rollback_error}")
            logger.error(f"❌ DATABASE: Ошибка выполнения запроса: {e}")
            raise e
    
    try:
        return pool.retry_operation_sync(execute)
    except Exception as e:
        logger.error(f"❌ DATABASE: Ошибка выполнения запроса: {e}")
        raise


def execute_transaction(operations: List[callable]):
    """
    Выполняет транзакцию с несколькими операциями.
    
    Args:
        operations: Список функций для выполнения в транзакции
    """
    pool = get_session_pool()
    
    def execute_all(session):
        # Создаем новую транзакцию для каждой операции
        tx = session.transaction()
        try:
            results = []
            for operation in operations:
                result = operation(session, tx)
                results.append(result)
            tx.commit()
            logger.info(f"✅ DATABASE: Транзакция с {len(operations)} операциями выполнена успешно")
            return results
        except Exception as e:
            # При ошибке откатываем транзакцию
            try:
                tx.rollback()
            except Exception as rollback_error:
                logger.warning(f"⚠️ DATABASE: Ошибка при откате транзакции: {rollback_error}")
            logger.error(f"❌ DATABASE: Ошибка выполнения транзакции: {e}")
            raise e
    
    try:
        return pool.retry_operation_sync(execute_all)
    except Exception as e:
        logger.error(f"❌ DATABASE: Ошибка выполнения транзакции: {e}")
        raise


def upsert_record(table: str, data: Dict[str, Any]) -> None:
    """
    Вставляет или обновляет запись в таблице.
    
    Args:
        table: Название таблицы
        data: Данные для вставки/обновления
    """
    from datetime import datetime
    pool = get_session_pool()
    
    def upsert(session):
        # Создаем новую транзакцию для каждой операции
        tx = session.transaction()
        try:
            # Формируем запрос UPSERT
            columns = list(data.keys())
            values = []
            
            for key, value in data.items():
                if isinstance(value, str):
                    escaped_value = value.replace("'", "''")
                    values.append(f"'{escaped_value}'")
                elif isinstance(value, (int, float)):
                    values.append(str(value))
                elif isinstance(value, datetime):
                    # Для datetime объектов используем правильный формат для YDB
                    # YDB требует формат с часовым поясом
                    iso_format = value.strftime('%Y-%m-%dT%H:%M:%SZ')
                    values.append(f"Timestamp('{iso_format}')")
                elif isinstance(value, type(datetime.now().date())):
                    # Для date объектов используем правильный формат для YDB
                    date_format = value.strftime('%Y-%m-%d')
                    values.append(f"Date('{date_format}')")
                elif value is None:
                    values.append('NULL')
                else:
                    escaped_value = str(value).replace("'", "''")
                    values.append(f"'{escaped_value}'")
            
            query = f"""
                UPSERT INTO {table} ({', '.join(columns)})
                VALUES ({', '.join(values)})
            """
            
            prepared = session.prepare(query)
            tx.execute(prepared)
            tx.commit()
            logger.info(f"✅ DATABASE: UPSERT выполнен успешно в таблицу {table}")
        except Exception as e:
            # При ошибке откатываем транзакцию
            try:
                tx.rollback()
            except Exception as rollback_error:
                logger.warning(f"⚠️ DATABASE: Ошибка при откате транзакции: {rollback_error}")
            logger.error(f"❌ DATABASE: Ошибка upsert в таблицу {table}: {e}")
            raise e
    
    try:
        pool.retry_operation_sync(upsert)
    except Exception as e:
        logger.error(f"❌ DATABASE: Ошибка upsert в таблицу {table}: {e}")
        raise


def delete_record(table: str, where_clause: str) -> None:
    """
    Удаляет запись из таблицы.
    
    Args:
        table: Название таблицы
        where_clause: Условие WHERE
    """
    pool = get_session_pool()
    
    def delete(session):
        # Создаем новую транзакцию для каждой операции
        tx = session.transaction()
        try:
            query = f"DELETE FROM {table} WHERE {where_clause}"
            prepared = session.prepare(query)
            tx.execute(prepared)
            tx.commit()
            logger.info(f"✅ DATABASE: DELETE выполнен успешно из таблицы {table}")
        except Exception as e:
            # При ошибке откатываем транзакцию
            try:
                tx.rollback()
            except Exception as rollback_error:
                logger.warning(f"⚠️ DATABASE: Ошибка при откате транзакции: {rollback_error}")
            logger.error(f"❌ DATABASE: Ошибка удаления из таблицы {table}: {e}")
            raise e
    
    try:
        pool.retry_operation_sync(delete)
    except Exception as e:
        logger.error(f"❌ DATABASE: Ошибка удаления из таблицы {table}: {e}")
        raise


def get_all_services() -> List[Dict[str, Any]]:
    """Получает все услуги из базы данных."""
    query = "SELECT * FROM services ORDER BY name"
    rows = execute_query(query)
    
    services = []
    for row in rows:
        services.append({
            'id': row[0],
            'name': row[1],
            'description': row[2],
            'price': row[3],
            'duration_minutes': row[4]
        })
    
    return services


def get_all_masters() -> List[Dict[str, Any]]:
    """Получает всех мастеров из базы данных."""
    query = "SELECT * FROM masters ORDER BY name"
    rows = execute_query(query)
    
    masters = []
    for row in rows:
        masters.append({
            'id': row[0],
            'name': row[1],
            'specialization': row[2]
        })
    
    return masters


def get_master_services(master_id: int) -> List[Dict[str, Any]]:
    """Получает услуги конкретного мастера."""
    query = f"""
        SELECT s.* FROM services s
        JOIN master_services ms ON s.id = ms.service_id
        WHERE ms.master_id = {master_id}
    """
    rows = execute_query(query)
    
    services = []
    for row in rows:
        services.append({
            'id': row[0],
            'name': row[1],
            'description': row[2],
            'price': row[3],
            'duration_minutes': row[4]
        })
    
    return services


def get_client_by_telegram_id(telegram_id: int) -> Optional[Dict[str, Any]]:
    """Получает клиента по Telegram ID."""
    query = f"SELECT * FROM clients WHERE telegram_id = {telegram_id}"
    rows = execute_query(query)
    
    if rows:
        row = rows[0]
        return {
            'id': row[0],
            'telegram_id': row[1],
            'first_name': row[2],
            'phone_number': row[3]
        }
    
    return None


def add_client(telegram_id: int, first_name: str = "", phone_number: str = "") -> int:
    """Добавляет нового клиента."""
    # Проверяем, существует ли клиент
    existing_client = get_client_by_telegram_id(telegram_id)
    if existing_client:
        return existing_client['id']
    
    # Получаем следующий ID
    query = "SELECT MAX(id) as max_id FROM clients"
    rows = execute_query(query)
    max_id = rows[0][0] if rows[0][0] is not None else 0
    new_id = max_id + 1
    
    # Добавляем клиента
    data = {
        'id': new_id,
        'telegram_id': telegram_id,
        'first_name': first_name,
        'phone_number': phone_number
    }
    
    upsert_record('clients', data)
    return new_id


def add_dialog_message(user_id: int, role: str, message_text: str) -> None:
    """Добавляет сообщение в историю диалогов."""
    from datetime import datetime
    
    # Получаем следующий ID
    query = "SELECT MAX(id) as max_id FROM dialog_history"
    rows = execute_query(query)
    max_id = rows[0][0] if rows[0][0] is not None else 0
    new_id = max_id + 1
    
    # Добавляем сообщение с правильным форматом timestamp для YDB
    data = {
        'id': new_id,
        'user_id': user_id,
        'role': role,
        'message_text': message_text,
        'timestamp': datetime.now()  # Передаем объект datetime, а не строку
    }
    
    upsert_record('dialog_history', data)


def init_database():
    """
    Инициализирует базу данных.
    Проверяет подключение и создает таблицы если необходимо.
    """
    try:
        logger.info("🗄️ DATABASE: Инициализация базы данных...")
        
        # Проверяем подключение
        driver = get_driver()
        logger.info("✅ DATABASE: Подключение к YDB проверено")
        
        # Проверяем существование основных таблиц
        tables_to_check = ['services', 'masters', 'clients', 'master_services', 'appointments', 'dialog_history', 'master_schedules']
        
        for table in tables_to_check:
            try:
                query = f"SELECT COUNT(*) FROM {table}"
                execute_query(query)
                logger.info(f"✅ DATABASE: Таблица {table} доступна")
            except Exception as e:
                logger.warning(f"⚠️ DATABASE: Таблица {table} недоступна: {e}")
        
        logger.info("✅ DATABASE: База данных успешно инициализирована")
        
    except Exception as e:
        logger.error(f"❌ DATABASE: Ошибка инициализации базы данных: {e}")
        raise


def close_database():
    """Закрывает соединение с базой данных."""
    global _driver, _session_pool
    
    if _session_pool:
        _session_pool.stop()
        _session_pool = None
    
    if _driver:
        _driver.stop()
        _driver = None
    
    logger.info("✅ DATABASE: Соединение с базой данных закрыто")