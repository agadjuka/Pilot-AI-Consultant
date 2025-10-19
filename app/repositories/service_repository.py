"""
Репозиторий для работы с услугами
"""

from typing import List, Optional, Dict, Any
from cachetools import TTLCache
from .base import BaseRepository
from app.core.database import execute_query

# Кэш для списка услуг, живет 10 минут (600 секунд)
services_cache = TTLCache(maxsize=1, ttl=600)


class ServiceRepository(BaseRepository):
    """Репозиторий для работы с услугами"""
    
    def __init__(self):
        super().__init__("services")
    
    def get_all(self, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        """Получает все услуги с кэшированием"""
        # Проверяем кэш только для полного списка (skip=0, limit=100)
        if skip == 0 and limit == 100:
            if 'all_services' in services_cache:
                # logger.info("Возвращаю список услуг из кэша!")  # Можешь добавить лог для отладки
                return services_cache['all_services']
        
        # Если данных нет в кэше или запрашивается не полный список, идем в БД
        query = f"SELECT * FROM {self.table_name} ORDER BY id LIMIT {limit} OFFSET {skip}"
        rows = execute_query(query)
        services = [self._row_to_dict(row) for row in rows]
        
        # Сохраняем в кэш только полный список
        if skip == 0 and limit == 100:
            services_cache['all_services'] = services
        
        return services
    
    def clear_cache(self) -> None:
        """Очищает кэш услуг"""
        services_cache.clear()
    
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
    
    def create(self, data: Dict[str, Any]) -> int:
        """Создает новую услугу и очищает кэш"""
        result = super().create(data)
        self.clear_cache()
        return result
    
    def update(self, id: Any, data: Dict[str, Any]) -> None:
        """Обновляет услугу и очищает кэш"""
        super().update(id, data)
        self.clear_cache()
    
    def delete(self, id: Any) -> None:
        """Удаляет услугу и очищает кэш"""
        super().delete(id)
        self.clear_cache()
    
    def _row_to_dict(self, row: tuple) -> Dict[str, Any]:
        """Конвертирует строку результата в словарь"""
        # Реальный порядок полей в YDB: [description, duration_minutes, id, name, price]
        return {
            'id': row[2],
            'name': row[3].decode('utf-8') if isinstance(row[3], bytes) else str(row[3]),
            'description': row[0].decode('utf-8') if isinstance(row[0], bytes) else str(row[0]),
            'price': row[4],
            'duration_minutes': row[1]
        }