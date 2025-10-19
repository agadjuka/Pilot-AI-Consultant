#!/usr/bin/env python3
"""
Полный перенос данных из SQLite в YDB
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
                
                # 1. Переносим services
                logger.info("📋 Переносим services...")
                sqlite_cursor.execute("SELECT id, name, description, price, duration_minutes FROM services")
                services_data = sqlite_cursor.fetchall()
                
                def insert_services(session):
                    for service in services_data:
                        # Используем простые значения вместо параметров
                        query = f"""
                            INSERT INTO services (id, name, description, price, duration_minutes)
                            VALUES ({service[0]}, '{service[1].replace("'", "''")}', '{service[2].replace("'", "''") if service[2] else ""}', {service[3]}, {service[4]})
                        """
                        prepared = session.prepare(query)
                        session.transaction().execute(prepared)
                
                pool.retry_operation_sync(insert_services)
                logger.info(f"✅ Перенесено {len(services_data)} услуг")
                
                # 2. Переносим masters
                logger.info("👥 Переносим masters...")
                sqlite_cursor.execute("SELECT id, name, specialization FROM masters")
                masters_data = sqlite_cursor.fetchall()
                
                def insert_masters(session):
                    prepared = session.prepare("""
                        INSERT INTO masters (id, name, specialization)
                        VALUES ($id, $name, $specialization)
                    """)
                    
                    for master in masters_data:
                        session.transaction().execute(prepared, {
                            '$id': master[0],
                            '$name': master[1],
                            '$specialization': master[2] if master[2] else ""
                        })
                
                pool.retry_operation_sync(insert_masters)
                logger.info(f"✅ Перенесено {len(masters_data)} мастеров")
                
                # 3. Переносим master_services
                logger.info("🔗 Переносим master_services...")
                sqlite_cursor.execute("SELECT master_id, service_id FROM master_services")
                master_services_data = sqlite_cursor.fetchall()
                
                def insert_master_services(session):
                    prepared = session.prepare("""
                        INSERT INTO master_services (master_id, service_id)
                        VALUES ($master_id, $service_id)
                    """)
                    
                    for ms in master_services_data:
                        session.transaction().execute(prepared, {
                            '$master_id': ms[0],
                            '$service_id': ms[1]
                        })
                
                pool.retry_operation_sync(insert_master_services)
                logger.info(f"✅ Перенесено {len(master_services_data)} связей мастер-услуга")
                
                # 4. Объединяем users и clients в clients
                logger.info("👤 Переносим clients (объединяем users и clients)...")
                
                # Получаем данные из обеих таблиц
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
                
                def insert_clients(session):
                    prepared = session.prepare("""
                        INSERT INTO clients (id, telegram_id, first_name, phone_number)
                        VALUES ($id, $telegram_id, $first_name, $phone_number)
                    """)
                    
                    for client_data in all_clients.values():
                        session.transaction().execute(prepared, {
                            '$id': client_data['id'],
                            '$telegram_id': client_data['telegram_id'],
                            '$first_name': client_data['first_name'] if client_data['first_name'] else "",
                            '$phone_number': client_data['phone_number'] if client_data['phone_number'] else ""
                        })
                
                pool.retry_operation_sync(insert_clients)
                logger.info(f"✅ Перенесено {len(all_clients)} клиентов")
                
                # 5. Переносим appointments (без google_event_id)
                logger.info("📅 Переносим appointments...")
                sqlite_cursor.execute("SELECT id, user_telegram_id, master_id, service_id, start_time, end_time FROM appointments")
                appointments_data = sqlite_cursor.fetchall()
                
                def insert_appointments(session):
                    prepared = session.prepare("""
                        INSERT INTO appointments (id, user_telegram_id, master_id, service_id, start_time, end_time)
                        VALUES ($id, $user_telegram_id, $master_id, $service_id, $start_time, $end_time)
                    """)
                    
                    for appointment in appointments_data:
                        # Конвертируем datetime строки в timestamp
                        start_time = datetime.fromisoformat(appointment[4].replace('Z', '+00:00'))
                        end_time = datetime.fromisoformat(appointment[5].replace('Z', '+00:00'))
                        
                        session.transaction().execute(prepared, {
                            '$id': appointment[0],
                            '$user_telegram_id': appointment[1],
                            '$master_id': appointment[2],
                            '$service_id': appointment[3],
                            '$start_time': start_time,
                            '$end_time': end_time
                        })
                
                pool.retry_operation_sync(insert_appointments)
                logger.info(f"✅ Перенесено {len(appointments_data)} записей")
                
                # 6. Переносим dialog_history
                logger.info("💬 Переносим dialog_history...")
                sqlite_cursor.execute("SELECT id, user_id, role, message_text, timestamp FROM dialog_history")
                dialog_data = sqlite_cursor.fetchall()
                
                def insert_dialog_history(session):
                    prepared = session.prepare("""
                        INSERT INTO dialog_history (id, user_id, role, message_text, timestamp)
                        VALUES ($id, $user_id, $role, $message_text, $timestamp)
                    """)
                    
                    for dialog in dialog_data:
                        # Конвертируем datetime строки в timestamp
                        timestamp = datetime.fromisoformat(dialog[4].replace('Z', '+00:00'))
                        
                        session.transaction().execute(prepared, {
                            '$id': dialog[0],
                            '$user_id': dialog[1],
                            '$role': dialog[2],
                            '$message_text': dialog[3],
                            '$timestamp': timestamp
                        })
                
                pool.retry_operation_sync(insert_dialog_history)
                logger.info(f"✅ Перенесено {len(dialog_data)} сообщений диалога")
                
                logger.info("🎉 Перенос данных завершен успешно!")
                
    except Exception as e:
        logger.error(f"❌ Ошибка переноса данных: {e}")
        raise
    finally:
        sqlite_conn.close()

if __name__ == "__main__":
    migrate_data_from_sqlite_to_ydb()
