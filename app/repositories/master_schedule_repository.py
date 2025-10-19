"""
Репозиторий для работы с графиками работы мастеров
"""

from typing import List, Optional, Dict, Any
from datetime import date
from .base import BaseRepository
from app.core.database import execute_query


class MasterScheduleRepository(BaseRepository):
    """Репозиторий для работы с графиками работы мастеров"""
    
    def __init__(self):
        super().__init__("master_schedules")
    
    def find_by_master_and_date(self, master_id: int, schedule_date: date) -> Optional[Dict[str, Any]]:
        """Находит график работы мастера на конкретную дату"""
        query = f"""
            SELECT * FROM {self.table_name} 
            WHERE master_id = {master_id} AND date = Date('{schedule_date}')
        """
        rows = execute_query(query)
        
        if rows:
            return self._row_to_dict(rows[0])
        return None
    
    def get_master_schedules_for_period(self, master_id: int, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """Получает графики работы мастера за период"""
        query = f"""
            SELECT * FROM {self.table_name} 
            WHERE master_id = {master_id} 
            AND date >= Date('{start_date}') 
            AND date <= Date('{end_date}')
            ORDER BY date
        """
        rows = execute_query(query)
        
        return [self._row_to_dict(row) for row in rows]
    
    def get_available_masters_for_date(self, schedule_date: date) -> List[Dict[str, Any]]:
        """Получает всех мастеров, которые работают в указанную дату"""
        query = f"""
            SELECT DISTINCT m.* FROM masters m
            JOIN {self.table_name} ms ON m.id = ms.master_id
            WHERE ms.date = Date('{schedule_date}')
        """
        rows = execute_query(query)
        
        masters = []
        for row in rows:
            masters.append({
                'id': row[0],
                'name': row[1].decode('utf-8') if isinstance(row[1], bytes) else str(row[1]),
                'specialization': row[2].decode('utf-8') if isinstance(row[2], bytes) else str(row[2])
            })
        
        return masters
    
    def create_schedule(self, master_id: int, schedule_date: date, start_time: str, end_time: str) -> int:
        """Создает новый график работы"""
        data = {
            'master_id': master_id,
            'date': schedule_date,
            'start_time': start_time,
            'end_time': end_time
        }
        return self.create(data)
    
    def _row_to_dict(self, row: tuple) -> Dict[str, Any]:
        """Конвертирует строку результата в словарь"""
        # Проверяем, что это словарь (результат execute_query)
        if isinstance(row, dict):
            return {
                'id': row['id'],
                'master_id': row['master_id'],
                'date': row['date'],
                'start_time': row['start_time'].decode('utf-8') if isinstance(row['start_time'], bytes) else str(row['start_time']),
                'end_time': row['end_time'].decode('utf-8') if isinstance(row['end_time'], bytes) else str(row['end_time'])
            }
        else:
            # Если это tuple, маппим по позициям
            return {
                'id': row[0],
                'master_id': row[1],
                'date': row[2],
                'start_time': row[3].decode('utf-8') if isinstance(row[3], bytes) else str(row[3]),
                'end_time': row[4].decode('utf-8') if isinstance(row[4], bytes) else str(row[4])
            }
