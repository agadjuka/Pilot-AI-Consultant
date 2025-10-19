"""
Репозиторий для работы с услугами
"""

from typing import List, Optional, Dict, Any
from .base import BaseRepository
from app.core.database import execute_query


class ServiceRepository(BaseRepository):
    """Репозиторий для работы с услугами"""
    
    def __init__(self):
        super().__init__("services")
    
    def get_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Получает услугу по названию"""
        escaped_name = name.replace("'", "''")
        query = f"SELECT * FROM {self.table_name} WHERE name = '{escaped_name}'"
        rows = execute_query(query)
        
        if rows:
            return self._row_to_dict(rows[0])
        return None
    
    def search_by_name(self, search_term: str) -> List[Dict[str, Any]]:
        """Ищет услуги по названию"""
        escaped_term = search_term.replace("'", "''")
        query = f"""
            SELECT * FROM {self.table_name} 
            WHERE name LIKE '%{escaped_term}%'
            ORDER BY name
        """
        rows = execute_query(query)
        
        return [self._row_to_dict(row) for row in rows]
    
    def get_by_price_range(self, min_price: float, max_price: float) -> List[Dict[str, Any]]:
        """Получает услуги в диапазоне цен"""
        query = f"""
            SELECT * FROM {self.table_name} 
            WHERE price >= {min_price} AND price <= {max_price}
            ORDER BY price
        """
        rows = execute_query(query)
        
        return [self._row_to_dict(row) for row in rows]
    
    def _row_to_dict(self, row: tuple) -> Dict[str, Any]:
        """Конвертирует строку результата в словарь"""
        return {
            'id': row[0],
            'name': row[1],
            'description': row[2],
            'price': row[3],
            'duration_minutes': row[4]
        }