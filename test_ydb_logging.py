#!/usr/bin/env python3
"""
Тестовый скрипт для проверки подавления логов YDB SDK.
"""

import logging
import sys
import os

# Добавляем путь к приложению
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

def test_ydb_logging_suppression():
    """Тестирует подавление логов YDB SDK."""
    
    print("🧪 ТЕСТ: Тестирование подавления логов YDB SDK")
    print("=" * 60)
    
    # Тест 1: Без подавления
    print("\n📋 ТЕСТ 1: Без подавления логов YDB")
    print("-" * 40)
    
    # Настраиваем логирование без подавления
    from app.core.logging_config import setup_logging
    setup_logging(level="INFO", suppress_ydb_tokens=False)
    
    # Имитируем сообщения YDB SDK
    ydb_logger = logging.getLogger('ydb.credentials.MetadataUrlCredentials')
    ydb_logger.info("Cached token reached refresh_in deadline, current time 1760935794.0680192, deadline 0")
    
    print("\n📋 ТЕСТ 2: С подавлением логов YDB")
    print("-" * 40)
    
    # Настраиваем логирование с подавлением
    setup_logging(level="INFO", suppress_ydb_tokens=True)
    
    # Имитируем сообщения YDB SDK (они не должны появиться)
    ydb_logger = logging.getLogger('ydb.credentials.MetadataUrlCredentials')
    ydb_logger.info("Cached token reached refresh_in deadline, current time 1760935794.0680192, deadline 0")
    
    # Но наши сообщения должны появляться
    app_logger = logging.getLogger('app.test')
    app_logger.info("Это сообщение от нашего приложения должно появиться")
    
    print("\n✅ ТЕСТ: Завершен")
    print("=" * 60)
    print("📝 РЕЗУЛЬТАТ:")
    print("   - В ТЕСТЕ 1: Сообщения YDB должны быть видны")
    print("   - В ТЕСТЕ 2: Сообщения YDB должны быть скрыты")
    print("   - В обоих тестах: Сообщения приложения должны быть видны")

if __name__ == "__main__":
    test_ydb_logging_suppression()
