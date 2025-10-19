#!/usr/bin/env python3
"""
Правильный перенос всех данных из SQLite в YDB
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

def migrate_all_data():
    """Переносит все данные из SQLite в YDB с правильным коммитом"""
    
    logger.info("🚀 Переносим ВСЕ данные из SQLite в YDB...")
    
    # Подключаемся к SQLite
    sqlite_conn = sqlite3.connect("beauty_salon.db")
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
                    tx = session.transaction()
                    try:
                        for service in services_data:
                            query = f"""
                                UPSERT INTO services (id, name, description, price, duration_minutes)
                                VALUES ({service[0]}, '{service[1].replace("'", "''")}', '{service[2].replace("'", "''") if service[2] else ""}', {service[3]}, {service[4]})
                            """
                            prepared = session.prepare(query)
                            tx.execute(prepared)
                        tx.commit()
                        logger.info(f"✅ Перенесено {len(services_data)} услуг")
                    except Exception as e:
                        tx.rollback()
                        raise e
                
                pool.retry_operation_sync(insert_services)
                
                # 2. Переносим masters
                logger.info("👥 Переносим masters...")
                sqlite_cursor.execute("SELECT id, name, specialization FROM masters")
                masters_data = sqlite_cursor.fetchall()
                
                def insert_masters(session):
                    tx = session.transaction()
                    try:
                        for master in masters_data:
                            query = f"""
                                UPSERT INTO masters (id, name, specialization)
                                VALUES ({master[0]}, '{master[1].replace("'", "''")}', '{master[2].replace("'", "''") if master[2] else ""}')
                            """
                            prepared = session.prepare(query)
                            tx.execute(prepared)
                        tx.commit()
                        logger.info(f"✅ Перенесено {len(masters_data)} мастеров")
                    except Exception as e:
                        tx.rollback()
                        raise e
                
                pool.retry_operation_sync(insert_masters)
                
                # 3. Переносим master_services
                logger.info("🔗 Переносим master_services...")
                sqlite_cursor.execute("SELECT master_id, service_id FROM master_services")
                master_services_data = sqlite_cursor.fetchall()
                
                def insert_master_services(session):
                    tx = session.transaction()
                    try:
                        for ms in master_services_data:
                            query = f"""
                                UPSERT INTO master_services (master_id, service_id)
                                VALUES ({ms[0]}, {ms[1]})
                            """
                            prepared = session.prepare(query)
                            tx.execute(prepared)
                        tx.commit()
                        logger.info(f"✅ Перенесено {len(master_services_data)} связей мастер-услуга")
                    except Exception as e:
                        tx.rollback()
                        raise e
                
                pool.retry_operation_sync(insert_master_services)
                
                # 4. Объединяем users и clients в clients
                logger.info("👤 Переносим clients (объединяем users и clients)...")
                
                sqlite_cursor.execute("SELECT id, telegram_id, first_name, phone_number FROM users")
                users_data = sqlite_cursor.fetchall()
                
                sqlite_cursor.execute("SELECT id, telegram_id, first_name, phone_number FROM clients")
                clients_data = sqlite_cursor.fetchall()
                
                # Объединяем данные
                all_clients = {}
                
                for user in users_data:
                    telegram_id = user[1]
                    if telegram_id not in all_clients:
                        all_clients[telegram_id] = {
                            'id': user[0],
                            'telegram_id': telegram_id,
                            'first_name': user[2],
                            'phone_number': user[3]
                        }
                
                for client in clients_data:
                    telegram_id = client[1]
                    all_clients[telegram_id] = {
                        'id': client[0],
                        'telegram_id': telegram_id,
                        'first_name': client[2],
                        'phone_number': client[3]
                    }
                
                def insert_clients(session):
                    tx = session.transaction()
                    try:
                        for client_data in all_clients.values():
                            query = f"""
                                UPSERT INTO clients (id, telegram_id, first_name, phone_number)
                                VALUES ({client_data['id']}, {client_data['telegram_id']}, '{client_data['first_name'].replace("'", "''") if client_data['first_name'] else ""}', '{client_data['phone_number'].replace("'", "''") if client_data['phone_number'] else ""}')
                            """
                            prepared = session.prepare(query)
                            tx.execute(prepared)
                        tx.commit()
                        logger.info(f"✅ Перенесено {len(all_clients)} клиентов")
                    except Exception as e:
                        tx.rollback()
                        raise e
                
                pool.retry_operation_sync(insert_clients)
                
                # 5. Переносим appointments
                logger.info("📅 Переносим appointments...")
                sqlite_cursor.execute("SELECT id, user_telegram_id, master_id, service_id, start_time, end_time FROM appointments")
                appointments_data = sqlite_cursor.fetchall()
                
                def insert_appointments(session):
                    tx = session.transaction()
                    try:
                        for appointment in appointments_data:
                            start_time = datetime.fromisoformat(appointment[4].replace('Z', '+00:00'))
                            end_time = datetime.fromisoformat(appointment[5].replace('Z', '+00:00'))
                            
                            query = f"""
                                UPSERT INTO appointments (id, user_telegram_id, master_id, service_id, start_time, end_time)
                                VALUES ({appointment[0]}, {appointment[1]}, {appointment[2]}, {appointment[3]}, '{start_time.isoformat()}', '{end_time.isoformat()}')
                            """
                            prepared = session.prepare(query)
                            tx.execute(prepared)
                        tx.commit()
                        logger.info(f"✅ Перенесено {len(appointments_data)} записей")
                    except Exception as e:
                        tx.rollback()
                        raise e
                
                pool.retry_operation_sync(insert_appointments)
                
                # 6. Переносим dialog_history
                logger.info("💬 Переносим dialog_history...")
                sqlite_cursor.execute("SELECT id, user_id, role, message_text, timestamp FROM dialog_history")
                dialog_data = sqlite_cursor.fetchall()
                
                def insert_dialog_history(session):
                    tx = session.transaction()
                    try:
                        for dialog in dialog_data:
                            timestamp = datetime.fromisoformat(dialog[4].replace('Z', '+00:00'))
                            
                            query = f"""
                                UPSERT INTO dialog_history (id, user_id, role, message_text, timestamp)
                                VALUES ({dialog[0]}, {dialog[1]}, '{dialog[2]}', '{dialog[3].replace("'", "''")}', '{timestamp.isoformat()}')
                            """
                            prepared = session.prepare(query)
                            tx.execute(prepared)
                        tx.commit()
                        logger.info(f"✅ Перенесено {len(dialog_data)} сообщений диалога")
                    except Exception as e:
                        tx.rollback()
                        raise e
                
                pool.retry_operation_sync(insert_dialog_history)
                
                logger.info("🎉 Перенос ВСЕХ данных завершен успешно!")
                
    except Exception as e:
        logger.error(f"❌ Ошибка переноса данных: {e}")
        raise
    finally:
        sqlite_conn.close()

if __name__ == "__main__":
    migrate_all_data()
