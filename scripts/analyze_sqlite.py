#!/usr/bin/env python3
"""
Анализ структуры SQLite базы данных
"""

import sqlite3
import os

def analyze_sqlite_database():
    """Анализирует структуру SQLite базы данных"""
    db_path = "beauty_salon.db"
    
    if not os.path.exists(db_path):
        print(f"❌ База данных {db_path} не найдена")
        return
    
    print(f"🔍 Анализируем базу данных: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Получаем список всех таблиц
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        print(f"\n📋 Найдено таблиц: {len(tables)}")
        
        for table_name in tables:
            table_name = table_name[0]
            print(f"\n--- Таблица: {table_name} ---")
            
            # Получаем структуру таблицы
            cursor.execute(f"PRAGMA table_info({table_name});")
            columns = cursor.fetchall()
            
            print("Структура:")
            for col in columns:
                print(f"  {col[1]} {col[2]} {'NOT NULL' if col[3] else 'NULL'} {'PRIMARY KEY' if col[5] else ''}")
            
            # Получаем количество записей
            cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
            count = cursor.fetchone()[0]
            print(f"Записей: {count}")
            
            # Показываем первые несколько записей
            if count > 0:
                cursor.execute(f"SELECT * FROM {table_name} LIMIT 3;")
                rows = cursor.fetchall()
                print("Примеры записей:")
                for i, row in enumerate(rows, 1):
                    print(f"  {i}: {row}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Ошибка анализа: {e}")

if __name__ == "__main__":
    analyze_sqlite_database()
