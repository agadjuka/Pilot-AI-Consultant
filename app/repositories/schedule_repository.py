"""
Репозитории для работы с графиками работы мастеров
"""

from typing import List, Optional, Dict, Any
from datetime import date, time
from app.repositories.base import BaseRepository


class WorkScheduleRepository(BaseRepository):
    """Репозиторий для работы с графиками работы мастеров"""
    
    def __init__(self):
        super().__init__("work_schedules")
    
    def find_by_master_and_day(self, master_id: int, day_of_week: int) -> Optional[Dict[str, Any]]:
        """Находит график работы мастера для конкретного дня недели"""
        query = f"""
            SELECT * FROM {self.table_name} 
            WHERE master_id = {master_id} AND day_of_week = {day_of_week}
        """
        from app.core.database import execute_query
        rows = execute_query(query)
        
        if rows:
            return self._row_to_dict(rows[0])
        return None
    
    def find_by_master(self, master_id: int) -> List[Dict[str, Any]]:
        """Находит все графики работы мастера"""
        query = f"""
            SELECT * FROM {self.table_name} 
            WHERE master_id = {master_id}
            ORDER BY day_of_week
        """
        from app.core.database import execute_query
        rows = execute_query(query)
        
        return [self._row_to_dict(row) for row in rows]
    
    def _row_to_dict(self, row: tuple) -> Dict[str, Any]:
        """Преобразует строку результата в словарь"""
        return {
            'id': row[0],
            'master_id': row[1],
            'day_of_week': row[2],
            'start_time': row[3],
            'end_time': row[4]
        }


class ScheduleExceptionRepository(BaseRepository):
    """Репозиторий для работы с исключениями из графика работы"""
    
    def __init__(self):
        super().__init__("schedule_exceptions")
    
    def find_by_master_and_date(self, master_id: int, date: date) -> Optional[Dict[str, Any]]:
        """Находит исключение для мастера на конкретную дату"""
        query = f"""
            SELECT * FROM {self.table_name} 
            WHERE master_id = {master_id} AND date = Date('{date.isoformat()}')
        """
        from app.core.database import execute_query
        rows = execute_query(query)
        
        if rows:
            return self._row_to_dict(rows[0])
        return None
    
    def find_by_master(self, master_id: int) -> List[Dict[str, Any]]:
        """Находит все исключения мастера"""
        query = f"""
            SELECT * FROM {self.table_name} 
            WHERE master_id = {master_id}
            ORDER BY date
        """
        from app.core.database import execute_query
        rows = execute_query(query)
        
        return [self._row_to_dict(row) for row in rows]
    
    def find_by_date_range(self, master_id: int, start_date: date, end_date: date) -> List[Dict[str, Any]]:
        """Находит исключения мастера в диапазоне дат"""
        query = f"""
            SELECT * FROM {self.table_name} 
            WHERE master_id = {master_id} 
            AND date >= Date('{start_date.isoformat()}') 
            AND date <= Date('{end_date.isoformat()}')
            ORDER BY date
        """
        from app.core.database import execute_query
        rows = execute_query(query)
        
        return [self._row_to_dict(row) for row in rows]
    
    def _row_to_dict(self, row: tuple) -> Dict[str, Any]:
        """Преобразует строку результата в словарь"""
        return {
            'id': row[0],
            'master_id': row[1],
            'date': row[2],
            'is_day_off': row[3],
            'start_time': row[4],
            'end_time': row[5]
        }
