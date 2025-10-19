#!/usr/bin/env python3
"""
Простой и эффективный перенос данных из SQLite в YDB
Работает по одной таблице за раз
"""

import os
import sys
import sqlite3
from datetime import datetime
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

def migrate_table_data(table_name, sqlite_cursor, pool):
    """Переносит данные одной таблицы из SQLite в YDB"""
    
    logger.info(f"📋 Переносим таблицу {table_name}...")
    
    try:
        # Получаем данные из SQLite
        if table_name == "services":
            sqlite_cursor.execute("SELECT id, name, description, price, duration_minutes FROM services")
            data = sqlite_cursor.fetchall()
            
            def insert_data(session):
                for row in data:
                    query = f"""
                        INSERT INTO services (id, name, description, price, duration_minutes)
                        VALUES ({row[0]}, '{row[1].replace("'", "''")}', '{row[2].replace("'", "''") if row[2] else ""}', {row[3]}, {row[4]})
                    """
                    prepared = session.prepare(query)
                    session.transaction().execute(prepared)
            
            pool.retry_operation_sync(insert_data)
            logger.info(f"✅ Перенесено {len(data)} записей в {table_name}")
            
        elif table_name == "masters":
            sqlite_cursor.execute("SELECT id, name, specialization FROM masters")
            data = sqlite_cursor.fetchall()
            
            def insert_data(session):
                for row in data:
                    query = f"""
                        INSERT INTO masters (id, name, specialization)
                        VALUES ({row[0]}, '{row[1].replace("'", "''")}', '{row[2].replace("'", "''") if row[2] else ""}')
                    """
                    prepared = session.prepare(query)
                    session.transaction().execute(prepared)
            
            pool.retry_operation_sync(insert_data)
            logger.info(f"✅ Перенесено {len(data)} записей в {table_name}")
            
        elif table_name == "master_services":
            sqlite_cursor.execute("SELECT master_id, service_id FROM master_services")
            data = sqlite_cursor.fetchall()
            
            def insert_data(session):
                for row in data:
                    query = f"""
                        INSERT INTO master_services (master_id, service_id)
                        VALUES ({row[0]}, {row[1]})
                    """
                    prepared = session.prepare(query)
                    session.transaction().execute(prepared)
            
            pool.retry_operation_sync(insert_data)
            logger.info(f"✅ Перенесено {len(data)} записей в {table_name}")
            
        elif table_name == "clients":
            # Объединяем users и clients
            sqlite_cursor.execute("SELECT id, telegram_id, first_name, phone_number FROM users")
            users_data = sqlite_cursor.fetchall()
            
            sqlite_cursor.execute("SELECT id, telegram_id, first_name, phone_number FROM clients")
            clients_data = sqlite_cursor.fetchall()
            
            # Объединяем данные, избегая дублирования по telegram_id
            all_clients = {}
            
            # Добавляем users
            for user in users_data:
                telegram_id = user[1]
                if telegram_id not in all_clients:
                    all_clients[telegram_id] = {
                        'id': user[0],
                        'telegram_id': telegram_id,
                        'first_name': user[2],
                        'phone_number': user[3]
                    }
            
            # Добавляем clients (приоритет у clients, если есть конфликт)
            for client in clients_data:
                telegram_id = client[1]
                all_clients[telegram_id] = {
                    'id': client[0],
                    'telegram_id': telegram_id,
                    'first_name': client[2],
                    'phone_number': client[3]
                }
            
            def insert_data(session):
                for client_data in all_clients.values():
                    query = f"""
                        INSERT INTO clients (id, telegram_id, first_name, phone_number)
                        VALUES ({client_data['id']}, {client_data['telegram_id']}, '{client_data['first_name'].replace("'", "''") if client_data['first_name'] else ""}', '{client_data['phone_number'].replace("'", "''") if client_data['phone_number'] else ""}')
                    """
                    prepared = session.prepare(query)
                    session.transaction().execute(prepared)
            
            pool.retry_operation_sync(insert_data)
            logger.info(f"✅ Перенесено {len(all_clients)} записей в {table_name}")
            
        elif table_name == "appointments":
            sqlite_cursor.execute("SELECT id, user_telegram_id, master_id, service_id, start_time, end_time FROM appointments")
            data = sqlite_cursor.fetchall()
            
            def insert_data(session):
                for row in data:
                    # Конвертируем datetime строки в timestamp
                    start_time = datetime.fromisoformat(row[4].replace('Z', '+00:00'))
                    end_time = datetime.fromisoformat(row[5].replace('Z', '+00:00'))
                    
                    query = f"""
                        INSERT INTO appointments (id, user_telegram_id, master_id, service_id, start_time, end_time)
                        VALUES ({row[0]}, {row[1]}, {row[2]}, {row[3]}, '{start_time.isoformat()}', '{end_time.isoformat()}')
                    """
                    prepared = session.prepare(query)
                    session.transaction().execute(prepared)
            
            pool.retry_operation_sync(insert_data)
            logger.info(f"✅ Перенесено {len(data)} записей в {table_name}")
            
        elif table_name == "dialog_history":
            sqlite_cursor.execute("SELECT id, user_id, role, message_text, timestamp FROM dialog_history")
            data = sqlite_cursor.fetchall()
            
            def insert_data(session):
                for row in data:
                    # Конвертируем datetime строки в timestamp
                    timestamp = datetime.fromisoformat(row[4].replace('Z', '+00:00'))
                    
                    query = f"""
                        INSERT INTO dialog_history (id, user_id, role, message_text, timestamp)
                        VALUES ({row[0]}, {row[1]}, '{row[2]}', '{row[3].replace("'", "''")}', '{timestamp.isoformat()}')
                    """
                    prepared = session.prepare(query)
                    session.transaction().execute(prepared)
            
            pool.retry_operation_sync(insert_data)
            logger.info(f"✅ Перенесено {len(data)} записей в {table_name}")
            
    except Exception as e:
        logger.error(f"❌ Ошибка переноса таблицы {table_name}: {e}")
        raise

def migrate_data_from_sqlite_to_ydb():
    """Переносит все данные из SQLite в YDB"""
    
    # Проверяем SQLite базу
    sqlite_path = "beauty_salon.db"
    if not os.path.exists(sqlite_path):
        logger.error(f"❌ SQLite база {sqlite_path} не найдена")
        return
    
    logger.info("🚀 Начинаем перенос данных из SQLite в YDB...")
    
    # Подключаемся к SQLite
    sqlite_conn = sqlite3.connect(sqlite_path)
    sqlite_cursor = sqlite_conn.cursor()
    
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
                
                # Переносим таблицы по порядку
                tables = ['services', 'masters', 'master_services', 'clients', 'appointments', 'dialog_history']
                
                for table in tables:
                    migrate_table_data(table, sqlite_cursor, pool)
                    logger.info(f"⏳ Пауза 2 секунды перед следующей таблицей...")
                    import time
                    time.sleep(2)
                
                logger.info("🎉 Перенос данных завершен успешно!")
                
    except Exception as e:
        logger.error(f"❌ Ошибка переноса данных: {e}")
        raise
    finally:
        sqlite_conn.close()

if __name__ == "__main__":
    migrate_data_from_sqlite_to_ydb()
