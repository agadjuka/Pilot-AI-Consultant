"""
Базовый репозиторий для работы с YDB
"""

from typing import Any, List, Optional, Dict
from app.core.database import execute_query, upsert_record, delete_record


class BaseRepository:
    """Базовый репозиторий для работы с YDB"""
    
    def __init__(self, table_name: str):
        self.table_name = table_name
    
    def get_by_id(self, id: Any) -> Optional[Dict[str, Any]]:
        """Получает запись по ID"""
        query = f"SELECT * FROM {self.table_name} WHERE id = {id}"
        rows = execute_query(query)
        
        if rows:
            return self._row_to_dict(rows[0])
        return None
    
    def get_all(self, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        """Получает все записи с пагинацией"""
        query = f"SELECT * FROM {self.table_name} ORDER BY id LIMIT {limit} OFFSET {skip}"
        rows = execute_query(query)
        
        return [self._row_to_dict(row) for row in rows]
    
    def create(self, data: Dict[str, Any]) -> int:
        """Создает новую запись"""
        # Получаем следующий ID
        query = f"SELECT MAX(id) as max_id FROM {self.table_name}"
        rows = execute_query(query)
        max_id = rows[0][0] if rows[0][0] is not None else 0
        new_id = max_id + 1
        
        data['id'] = new_id
        upsert_record(self.table_name, data)
        return new_id
    
    def update(self, id: Any, data: Dict[str, Any]) -> None:
        """Обновляет запись"""
        data['id'] = id
        upsert_record(self.table_name, data)
    
    def delete(self, id: Any) -> None:
        """Удаляет запись по ID"""
        delete_record(self.table_name, f"id = {id}")
    
    def _row_to_dict(self, row: tuple) -> Dict[str, Any]:
        """Конвертирует строку результата в словарь"""
        # Это базовый метод, должен быть переопределен в наследниках
        return {"id": row[0]}