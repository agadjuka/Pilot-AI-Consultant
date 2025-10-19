"""
Репозиторий для работы с историей диалогов
"""

from typing import List, Optional, Dict, Any
from .base import BaseRepository
from app.core.database import execute_query, upsert_record, delete_record


class DialogHistoryRepository(BaseRepository):
    """Репозиторий для работы с историей диалогов"""

    def __init__(self):
        super().__init__("dialog_history")

    def get_recent_messages(self, user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Получает последние N сообщений для указанного пользователя,
        отсортированных по времени (от старых к новым).
        
        Args:
            user_id: ID пользователя Telegram
            limit: Максимальное количество сообщений для получения
            
        Returns:
            Список сообщений
        """
        query = f"""
            SELECT * FROM {self.table_name} 
            WHERE user_id = {user_id}
            ORDER BY timestamp DESC
            LIMIT {limit}
        """
        rows = execute_query(query)
        
        # Возвращаем в хронологическом порядке (от старых к новым)
        messages = [self._row_to_dict(row) for row in reversed(rows)]
        return messages

    def add_message(self, user_id: int, role: str, message_text: str) -> Dict[str, Any]:
        """
        Добавляет новое сообщение в историю диалога.
        
        Args:
            user_id: ID пользователя Telegram
            role: Роль отправителя ('user' или 'model')
            message_text: Текст сообщения
            
        Returns:
            Созданное сообщение
        """
        from datetime import datetime
        
        # Получаем следующий ID
        query = f"SELECT MAX(id) as max_id FROM {self.table_name}"
        rows = execute_query(query)
        max_id = rows[0][0] if rows[0][0] is not None else 0
        new_id = max_id + 1
        
        # Добавляем сообщение
        data = {
            'id': new_id,
            'user_id': user_id,
            'role': role,
            'message_text': message_text,
            'timestamp': datetime.now()  # Передаем объект datetime, а не строку
        }
        
        upsert_record(self.table_name, data)
        return self.get_by_id(new_id)

    def clear_user_history(self, user_id: int) -> int:
        """
        Удаляет всю историю диалога для указанного пользователя.
        
        Args:
            user_id: ID пользователя Telegram
            
        Returns:
            Количество удаленных записей
        """
        # Сначала считаем количество записей
        query = f"SELECT COUNT(*) FROM {self.table_name} WHERE user_id = {user_id}"
        rows = execute_query(query)
        count = rows[0][0]
        
        # Удаляем записи
        delete_record(self.table_name, f"user_id = {user_id}")
        
        return count

    def get_message_count(self, user_id: int) -> int:
        """Получает количество сообщений пользователя"""
        query = f"SELECT COUNT(*) FROM {self.table_name} WHERE user_id = {user_id}"
        rows = execute_query(query)
        return rows[0][0]

    def get_last_message(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Получает последнее сообщение пользователя"""
        query = f"""
            SELECT * FROM {self.table_name} 
            WHERE user_id = {user_id}
            ORDER BY timestamp DESC
            LIMIT 1
        """
        rows = execute_query(query)
        
        if rows:
            return self._row_to_dict(rows[0])
        return None

    def _row_to_dict(self, row: tuple) -> Dict[str, Any]:
        """Конвертирует строку результата в словарь"""
        return {
            'id': row[0],
            'user_id': row[1],
            'role': row[2],
            'message_text': row[3],
            'timestamp': row[4]
        }