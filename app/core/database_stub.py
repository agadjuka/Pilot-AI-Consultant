"""
Временная заглушка для работы с базой данных.
Используется для тестирования webhook'ов когда БД не настроена.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class DatabaseStub:
    """
    Заглушка для работы с базой данных.
    Все методы возвращают заглушки или пустые результаты.
    """
    
    def __init__(self):
        logger.info("🔧 STUB: DatabaseStub инициализирован (режим без БД)")
    
    def get_session_local(self):
        """
        Возвращает заглушку сессии базы данных.
        
        Returns:
            Заглушка сессии БД
        """
        logger.info("🗄️ STUB: Получение заглушки сессии БД")
        return DatabaseSessionStub()
    
    def get_engine(self):
        """
        Возвращает заглушку движка базы данных.
        
        Returns:
            Заглушка движка БД
        """
        logger.info("⚙️ STUB: Получение заглушки движка БД")
        return None


class DatabaseSessionStub:
    """
    Заглушка сессии базы данных.
    """
    
    def __init__(self):
        logger.info("🔧 STUB: DatabaseSessionStub инициализирован")
    
    def close(self):
        """
        Заглушка для закрытия сессии.
        """
        logger.info("🔒 STUB: Закрытие заглушки сессии БД")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Глобальная заглушка
_database_stub = DatabaseStub()


def get_session_local_stub():
    """
    Получить заглушку сессии базы данных.
    
    Returns:
        Заглушка сессии БД
    """
    return _database_stub.get_session_local()
