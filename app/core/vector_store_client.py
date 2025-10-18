"""
Централизованный клиент для работы с ChromaDB.
Поддерживает два режима: серверный (через Docker) и локальный файловый.
"""

import chromadb
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)


def get_chroma_client():
    """
    Создает и возвращает клиент ChromaDB.
    
    Режимы работы:
    - Если установлена CHROMA_HOST: подключается к серверу ChromaDB
    - Если НЕ установлена: использует локальный файловый режим
    """
    
    if settings.CHROMA_HOST:
        # Серверный режим - подключение к Docker-контейнеру
        logger.info(f"🔗 Подключение к ChromaDB серверу: {settings.CHROMA_HOST}:8000")
        return chromadb.HttpClient(host=settings.CHROMA_HOST, port=8000)
    else:
        # Локальный режим - файловое хранение
        logger.info("📁 Использование локального файлового режима ChromaDB")
        return chromadb.PersistentClient(path="./chroma_db_local")


# Глобальный экземпляр клиента
chroma_client = get_chroma_client()
