#!/usr/bin/env python3
"""
Тест подключения через SQLAlchemy + YDB (как в database.py)
"""

import os
import sys
from dotenv import load_dotenv

# Добавляем корень проекта в путь
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Загружаем переменные окружения
load_dotenv()

from sqlalchemy import create_engine
import ydb

def test_sqlalchemy_ydb_connection():
    """Тестирует подключение через SQLAlchemy + YDB"""
    print("🚀 Запускаем тест подключения через SQLAlchemy + YDB...")
    
    # Получаем настройки
    from app.core.config import settings
    
    endpoint = settings.YDB_ENDPOINT
    database = settings.YDB_DATABASE
    service_account_key_file = os.getenv("YC_SERVICE_ACCOUNT_KEY_FILE", "key.json")
    
    print(f"Подключаемся к эндпоинту: {endpoint}")
    print(f"База данных: {database}")
    print(f"Ключ сервисного аккаунта: {service_account_key_file}")
    
    # Проверяем существование файла ключа
    key_file_path = service_account_key_file
    if not os.path.exists(key_file_path):
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        key_file_path = os.path.join(project_root, service_account_key_file)
    
    if not os.path.exists(key_file_path):
        print(f"❌ Ошибка: Файл ключа {service_account_key_file} не найден.")
        return
    
    print(f"Найден файл ключа: {os.path.abspath(key_file_path)}")
    
    try:
        # Формируем строку подключения
        endpoint_clean = endpoint.replace('grpcs://', '').replace('grpc://', '')
        connection_string = f"ydb://{endpoint_clean}/{database}"
        
        # Получаем учетные данные
        credentials = ydb.iam.ServiceAccountCredentials.from_file(key_file_path)
        
        # Создаем engine
        engine = create_engine(
            connection_string,
            connect_args={"credentials": credentials}
        )
        
        # Тестируем подключение
        with engine.connect() as connection:
            result = connection.execute("SELECT 1 as test")
            row = result.fetchone()
            print(f"✅ УСПЕХ! Результат тестового запроса: {row[0]}")
            
    except Exception as e:
        print(f"❌ ОШИБКА ПОДКЛЮЧЕНИЯ:")
        print(e)

if __name__ == "__main__":
    test_sqlalchemy_ydb_connection()
