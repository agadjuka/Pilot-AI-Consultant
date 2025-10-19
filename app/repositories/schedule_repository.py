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
        # Проверяем типы данных и правильно их маппим
        id_val = row[0]
        master_id_val = row[1]
        day_of_week_val = row[2]
        start_time_val = row[3]
        end_time_val = row[4]
        
        # Определяем правильные значения на основе типов
        master_id = None
        day_of_week = None
        start_time = None
        end_time = None
        
        # Ищем master_id (должен быть int, но не слишком большим)
        for val in [master_id_val, day_of_week_val]:
            if isinstance(val, int) and val < 100:  # Разумный диапазон для master_id
                master_id = val
                break
        
        # Ищем day_of_week (должен быть int от 0 до 6)
        for val in [master_id_val, day_of_week_val]:
            if isinstance(val, int) and 0 <= val <= 6:
                day_of_week = val
                break
        
        # Если не нашли day_of_week среди первых двух, ищем среди всех
        if day_of_week is None:
            for val in [master_id_val, day_of_week_val, start_time_val, end_time_val]:
                if isinstance(val, int) and 0 <= val <= 6:
                    day_of_week = val
                    break
        
        # Ищем start_time и end_time (должны быть time или байты времени)
        time_values = []
        for val in [master_id_val, day_of_week_val, start_time_val, end_time_val]:
            if isinstance(val, time) or isinstance(val, bytes):
                time_values.append(val)
        
        # Конвертируем время
        if len(time_values) >= 2:
            start_time_raw = time_values[0]
            end_time_raw = time_values[1]
            
            if isinstance(start_time_raw, bytes):
                start_time_str = start_time_raw.decode('utf-8')
                start_time = time.fromisoformat(start_time_str)
            elif isinstance(start_time_raw, time):
                start_time = start_time_raw
            elif isinstance(start_time_raw, int):
                # Если это число, возможно это часы
                start_time = time(start_time_raw, 0)
                
            if isinstance(end_time_raw, bytes):
                end_time_str = end_time_raw.decode('utf-8')
                end_time = time.fromisoformat(end_time_str)
            elif isinstance(end_time_raw, time):
                end_time = end_time_raw
            elif isinstance(end_time_raw, int):
                # Если это число, возможно это часы
                end_time = time(end_time_raw, 0)
        
        return {
            'id': id_val,
            'master_id': master_id,
            'day_of_week': day_of_week,
            'start_time': start_time,
            'end_time': end_time
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
        # Конвертируем время из байтов в объекты time (если есть)
        start_time = None
        end_time = None
        
        if len(row) > 4 and row[4] is not None:  # start_time
            start_time_raw = row[4]
            if isinstance(start_time_raw, bytes):
                start_time_str = start_time_raw.decode('utf-8')
                start_time = time.fromisoformat(start_time_str)
            else:
                start_time = start_time_raw
                
        if len(row) > 5 and row[5] is not None:  # end_time
            end_time_raw = row[5]
            if isinstance(end_time_raw, bytes):
                end_time_str = end_time_raw.decode('utf-8')
                end_time = time.fromisoformat(end_time_str)
            else:
                end_time = end_time_raw
        
        return {
            'id': row[0],
            'master_id': row[1],
            'date': row[2],
            'is_day_off': row[3],
            'start_time': start_time,
            'end_time': end_time
        }
