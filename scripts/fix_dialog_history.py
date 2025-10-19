#!/usr/bin/env python3
"""
Исправление dialog_history с правильными типами данных
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

def fix_dialog_history():
    """Исправляет перенос dialog_history с правильными типами"""
    
    logger.info("🔧 Исправляем dialog_history...")
    
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
                
                # Получаем данные из SQLite
                sqlite_cursor.execute("SELECT id, user_id, role, message_text, timestamp FROM dialog_history")
                dialog_data = sqlite_cursor.fetchall()
                
                logger.info(f"📋 Найдено {len(dialog_data)} сообщений в SQLite")
                
                def insert_dialog_history(session):
                    tx = session.transaction()
                    try:
                        for dialog in dialog_data:
                            # Конвертируем datetime в timestamp правильно
                            timestamp = datetime.fromisoformat(dialog[4].replace('Z', '+00:00'))
                            
                            # Используем правильный синтаксис для Timestamp
                            query = f"""
                                UPSERT INTO dialog_history (id, user_id, role, message_text, timestamp)
                                VALUES ({dialog[0]}, {dialog[1]}, '{dialog[2]}', '{dialog[3].replace("'", "''")}', Timestamp('{timestamp.isoformat()}'))
                            """
                            prepared = session.prepare(query)
                            tx.execute(prepared)
                        tx.commit()
                        logger.info(f"✅ Перенесено {len(dialog_data)} сообщений диалога")
                    except Exception as e:
                        tx.rollback()
                        logger.error(f"❌ Ошибка: {e}")
                        raise e
                
                pool.retry_operation_sync(insert_dialog_history)
                
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        raise
    finally:
        sqlite_conn.close()

if __name__ == "__main__":
    fix_dialog_history()
