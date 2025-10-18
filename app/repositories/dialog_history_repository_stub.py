"""
Временная заглушка для DialogHistoryRepository без базы данных.
Используется для тестирования webhook'ов когда БД не настроена.
"""
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class DialogHistoryRepositoryStub:
    """
    Заглушка DialogHistoryRepository для работы без базы данных.
    Все методы возвращают пустые результаты или заглушки.
    """
    
    def __init__(self, db_session=None):
        """
        Инициализация заглушки.
        db_session игнорируется для совместимости с оригинальным API.
        """
        self.db_session = db_session
    
    def get_user_history(self, user_id: int, limit: int = 10) -> List[Dict]:
        """
        Заглушка для получения истории пользователя.
        
        Args:
            user_id: ID пользователя
            limit: Максимальное количество записей
            
        Returns:
            Пустой список
        """
        return []
    
    def add_message(self, user_id: int, role: str, message_text: str) -> None:
        """
        Заглушка для добавления сообщения.
        
        Args:
            user_id: ID пользователя
            role: Роль отправителя (user/bot)
            message_text: Текст сообщения
        """
        pass
    
    def clear_user_history(self, user_id: int) -> int:
        """
        Заглушка для очистки истории пользователя.
        
        Args:
            user_id: ID пользователя
            
        Returns:
            Количество "удаленных" записей (всегда 0 в заглушке)
        """
        return 0
