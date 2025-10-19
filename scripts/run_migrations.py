#!/usr/bin/env python3
"""
Скрипт для выполнения миграций YDB напрямую через SQLAlchemy
Обходит проблемы с Alembic и YDB
"""

import os
import sys
from dotenv import load_dotenv

# Добавляем корень проекта в путь
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Загружаем переменные окружения
load_dotenv()

from app.core.database import get_engine, Base
from app.models import *  # Импортируем все модели
import logging

# Настраиваем логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migrations():
    """Выполняет миграции напрямую через SQLAlchemy"""
    try:
        logger.info("🚀 Запускаем миграции YDB...")
        
        # Получаем engine
        engine = get_engine()
        
        # Создаем все таблицы
        logger.info("📋 Создаем таблицы...")
        Base.metadata.create_all(bind=engine)
        
        logger.info("✅ Миграции успешно выполнены!")
        
    except Exception as e:
        logger.error(f"❌ Ошибка выполнения миграций: {e}")
        raise

if __name__ == "__main__":
    run_migrations()
