"""
Репозиторий для работы с клиентами
"""

from typing import Optional, Dict, Any, List
from .base import BaseRepository
from app.core.database import execute_query, upsert_record


class ClientRepository(BaseRepository):
    """Репозиторий для работы с клиентами"""
    
    def __init__(self):
        super().__init__("clients")
    
    def get_by_telegram_id(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """Получает клиента по Telegram ID"""
        query = f"SELECT * FROM {self.table_name} WHERE telegram_id = {telegram_id}"
        rows = execute_query(query)
        
        if rows:
            return self._row_to_dict(rows[0])
        return None
    
    def get_or_create_by_telegram_id(self, telegram_id: int) -> Dict[str, Any]:
        """Получает или создает клиента по Telegram ID"""
        client = self.get_by_telegram_id(telegram_id)
        if client:
            return client
        
        # Создаем нового клиента
        new_id = self.create({
            'telegram_id': telegram_id,
            'first_name': '',
            'phone_number': ''
        })
        
        return self.get_by_id(new_id)
    
    def update_by_telegram_id(self, telegram_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Обновляет данные клиента по Telegram ID"""
        client = self.get_by_telegram_id(telegram_id)
        if not client:
            raise ValueError("Клиент не найден")
        
        # Обновляем данные
        data['telegram_id'] = telegram_id
        data['id'] = client['id']
        
        upsert_record(self.table_name, data)
        return self.get_by_id(client['id'])
    
    def search_by_name(self, search_term: str) -> List[Dict[str, Any]]:
        """Ищет клиентов по имени"""
        escaped_term = search_term.replace("'", "''")
        query = f"""
            SELECT * FROM {self.table_name} 
            WHERE first_name LIKE '%{escaped_term}%'
            ORDER BY first_name
        """
        rows = execute_query(query)
        
        return [self._row_to_dict(row) for row in rows]
    
    def get_by_phone(self, phone_number: str) -> Optional[Dict[str, Any]]:
        """Получает клиента по номеру телефона"""
        escaped_phone = phone_number.replace("'", "''")
        query = f"SELECT * FROM {self.table_name} WHERE phone_number = '{escaped_phone}'"
        rows = execute_query(query)
        
        if rows:
            return self._row_to_dict(rows[0])
        return None
    
    def _row_to_dict(self, row: tuple) -> Dict[str, Any]:
        """Конвертирует строку результата в словарь"""
        # Реальный порядок полей в YDB: [first_name, id, phone_number, telegram_id]
        return {
            'id': row[1],
            'telegram_id': row[3],
            'first_name': row[0].decode('utf-8') if isinstance(row[0], bytes) else str(row[0]),
            'phone_number': row[2].decode('utf-8') if isinstance(row[2], bytes) else str(row[2])
        }