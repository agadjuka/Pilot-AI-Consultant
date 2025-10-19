"""
Репозиторий для работы с мастерами
"""

from typing import List, Optional, Dict, Any
from .base import BaseRepository
from app.core.database import execute_query


class MasterRepository(BaseRepository):
    """Репозиторий для работы с мастерами"""
    
    def __init__(self):
        super().__init__("masters")
    
    def get_masters_for_service(self, service_id: int) -> List[Dict[str, Any]]:
        """Находит всех мастеров, которые выполняют указанную услугу"""
        query = f"""
            SELECT m.* FROM masters m
            JOIN master_services ms ON m.id = ms.master_id
            WHERE ms.service_id = {service_id}
            ORDER BY m.name
        """
        rows = execute_query(query)
        
        return [self._row_to_dict(row) for row in rows]
    
    def get_by_id_with_services(self, id: int) -> Optional[Dict[str, Any]]:
        """Находит мастера по ID и сразу подгружает связанные с ним услуги"""
        master = self.get_by_id(id)
        if master:
            master['services'] = self.get_master_services(id)
        return master
    
    def get_master_services(self, master_id: int) -> List[Dict[str, Any]]:
        """Получает услуги конкретного мастера"""
        query = f"""
            SELECT s.* FROM services s
            JOIN master_services ms ON s.id = ms.service_id
            WHERE ms.master_id = {master_id}
            ORDER BY s.name
        """
        rows = execute_query(query)
        
        services = []
        for row in rows:
            services.append({
                'id': row[0],
                'name': row[1],
                'description': row[2],
                'price': row[3],
                'duration_minutes': row[4]
            })
        
        return services
    
    def get_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Получает мастера по имени"""
        escaped_name = name.replace("'", "''")
        query = f"SELECT * FROM {self.table_name} WHERE name = '{escaped_name}'"
        rows = execute_query(query)
        
        if rows:
            return self._row_to_dict(rows[0])
        return None
    
    def search_by_name(self, search_term: str) -> List[Dict[str, Any]]:
        """Ищет мастеров по имени"""
        escaped_term = search_term.replace("'", "''")
        query = f"""
            SELECT * FROM {self.table_name} 
            WHERE name LIKE '%{escaped_term}%'
            ORDER BY name
        """
        rows = execute_query(query)
        
        return [self._row_to_dict(row) for row in rows]
    
    def get_by_specialization(self, specialization: str) -> List[Dict[str, Any]]:
        """Получает мастеров по специализации"""
        escaped_spec = specialization.replace("'", "''")
        query = f"""
            SELECT * FROM {self.table_name} 
            WHERE specialization = '{escaped_spec}'
            ORDER BY name
        """
        rows = execute_query(query)
        
        return [self._row_to_dict(row) for row in rows]
    
    def _row_to_dict(self, row: tuple) -> Dict[str, Any]:
        """Конвертирует строку результата в словарь"""
        return {
            'id': row[0],
            'name': row[1].decode('utf-8') if isinstance(row[1], bytes) else str(row[1]),
            'specialization': row[2].decode('utf-8') if isinstance(row[2], bytes) else str(row[2])
        }