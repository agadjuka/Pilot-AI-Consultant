#!/usr/bin/env python3
"""
Скрипт для наполнения ChromaDB базой знаний из файлов политик.
Использует централизованный клиент с поддержкой двух режимов работы.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv(os.getenv("ENV_FILE", ".env"))

# Импортируем централизованный клиент
from app.core.vector_store_client import chroma_client


def seed_knowledge_base():
    """Наполняет ChromaDB базой знаний из файлов политик."""
    
    print("🚀 Инициализация ChromaDB...")
    
    print("📚 Создание/получение коллекции 'salon_policies'...")
    
    # Создание или получение коллекции
    collection = chroma_client.get_or_create_collection(
        name="salon_policies",
        metadata={"description": "Политики поведения бота салона красоты"}
    )
    
    print("📁 Чтение файлов политик...")
    
    # Путь к директории с политиками
    knowledge_base_path = Path("knowledge_base")
    
    if not knowledge_base_path.exists():
        print("❌ Директория knowledge_base не найдена!")
        return
    
    # Чтение всех .txt файлов
    txt_files = list(knowledge_base_path.glob("*.txt"))
    
    if not txt_files:
        print("❌ Файлы политик не найдены в директории knowledge_base!")
        return
    
    documents = []
    ids = []
    
    for file_path in txt_files:
        print(f"📄 Обработка файла: {file_path.name}")
        
        # Чтение содержимого файла
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
        
        # Использование имени файла (без расширения) как ID
        file_id = file_path.stem
        
        documents.append(content)
        ids.append(file_id)
    
    print("💾 Добавление документов в ChromaDB...")
    
    # Добавление документов в коллекцию
    collection.add(
        documents=documents,
        ids=ids
    )
    
    print("✅ База знаний успешно наполнена!")
    print(f"📊 Добавлено документов: {len(documents)}")
    print("📋 Список политик:")
    for i, doc_id in enumerate(ids, 1):
        print(f"   {i}. {doc_id}")
    
    print("\n🎉 Готово! ChromaDB готова к использованию.")


if __name__ == "__main__":
    try:
        seed_knowledge_base()
    except Exception as e:
        print(f"❌ Ошибка при наполнении базы знаний: {e}")
        print("💡 Проверьте настройки ChromaDB в .env файле")
