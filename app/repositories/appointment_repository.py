"""
Репозиторий для работы с записями клиентов
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from .base import BaseRepository
from app.core.database import execute_query, upsert_record, delete_record


class AppointmentRepository(BaseRepository):
    """Репозиторий для работы с записями клиентов"""
    
    def __init__(self):
        super().__init__("appointments")
    
    def create(self, appointment_data: dict) -> Dict[str, Any]:
        """Создать новую запись"""
        # Получаем следующий ID
        query = f"SELECT MAX(id) as max_id FROM {self.table_name}"
        rows = execute_query(query)
        max_id = rows[0][0] if rows[0][0] is not None else 0
        new_id = max_id + 1
        
        appointment_data['id'] = new_id
        upsert_record(self.table_name, appointment_data)
        return self.get_by_id(new_id)
    
    def get_future_appointments_by_user(self, user_telegram_id: int) -> List[Dict[str, Any]]:
        """Получить все предстоящие записи пользователя"""
        now = datetime.now()
        # Используем правильный формат для YDB Timestamp
        now_str = now.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        query = f"""
            SELECT * FROM {self.table_name} 
            WHERE user_telegram_id = {user_telegram_id}
            AND start_time > Timestamp('{now_str}')
            ORDER BY start_time
        """
        rows = execute_query(query)
        
        return [self._row_to_dict(row) for row in rows]
    
    def get_next_appointment_by_user(self, user_telegram_id: int) -> Optional[Dict[str, Any]]:
        """Получить ближайшую предстоящую запись пользователя"""
        now = datetime.now()
        # Используем правильный формат для YDB Timestamp
        now_str = now.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        query = f"""
            SELECT * FROM {self.table_name} 
            WHERE user_telegram_id = {user_telegram_id}
            AND start_time > Timestamp('{now_str}')
            ORDER BY start_time
            LIMIT 1
        """
        rows = execute_query(query)
        
        if rows:
            return self._row_to_dict(rows[0])
        return None
    
    def check_duplicate_appointment(self, user_telegram_id: int, master_id: int, service_id: int, start_time: datetime) -> Optional[Dict[str, Any]]:
        """Проверить наличие дублирующейся записи"""
        start_time_str = start_time.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        query = f"""
            SELECT * FROM {self.table_name} 
            WHERE user_telegram_id = {user_telegram_id}
            AND master_id = {master_id}
            AND service_id = {service_id}
            AND start_time = Timestamp('{start_time_str}')
        """
        rows = execute_query(query)
        
        if rows:
            return self._row_to_dict(rows[0])
        return None
    
    def get_appointments_by_master(self, master_id: int, date: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """Получить записи мастера на определенную дату или все записи"""
        if date:
            date_str = date.strftime('%Y-%m-%d')
            query = f"""
                SELECT * FROM {self.table_name} 
                WHERE master_id = {master_id}
                AND CAST(start_time AS Date) = CAST('{date_str}' AS Date)
                ORDER BY start_time
            """
        else:
            query = f"""
                SELECT * FROM {self.table_name} 
                WHERE master_id = {master_id}
                ORDER BY start_time
            """
        
        rows = execute_query(query)
        return [self._row_to_dict(row) for row in rows]
    
    def get_appointments_by_date_range(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Получить записи в диапазоне дат"""
        start_str = start_date.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        end_str = end_date.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        
        query = f"""
            SELECT * FROM {self.table_name} 
            WHERE start_time >= Timestamp('{start_str}')
            AND start_time <= Timestamp('{end_str}')
            ORDER BY start_time
        """
        rows = execute_query(query)
        
        return [self._row_to_dict(row) for row in rows]
    
    def delete_by_id(self, appointment_id: int) -> bool:
        """Удалить запись по её первичному ключу"""
        try:
            delete_record(self.table_name, f"id = {appointment_id}")
            return True
        except Exception:
            return False
    
    def update(self, appointment_id: int, data: dict) -> Optional[Dict[str, Any]]:
        """Обновить запись по её первичному ключу"""
        appointment = self.get_by_id(appointment_id)
        if not appointment:
            return None
        
        data['id'] = appointment_id
        upsert_record(self.table_name, data)
        return self.get_by_id(appointment_id)
    
    def _row_to_dict(self, row: tuple) -> Dict[str, Any]:
        """Конвертирует строку результата в словарь"""
        from datetime import datetime
        
        # YDB возвращает поля в алфавитном порядке: end_time, id, master_id, service_id, start_time, user_telegram_id
        # Конвертируем время из микросекунд в datetime
        start_time = row[4]  # start_time
        end_time = row[0]    # end_time
        
        # Если это числа (микросекунды), конвертируем в datetime
        if isinstance(start_time, (int, float)):
            try:
                # YDB возвращает время в UTC, конвертируем в локальное время
                from datetime import timezone
                start_time = datetime.fromtimestamp(start_time / 1000000, tz=timezone.utc).replace(tzinfo=None)
            except (ValueError, OSError):
                # Если не удается конвертировать, оставляем как есть
                pass
        
        if isinstance(end_time, (int, float)):
            try:
                # YDB возвращает время в UTC, конвертируем в локальное время
                from datetime import timezone
                end_time = datetime.fromtimestamp(end_time / 1000000, tz=timezone.utc).replace(tzinfo=None)
            except (ValueError, OSError):
                # Если не удается конвертировать, оставляем как есть
                pass
        
        # Если это строки, пытаемся парсить
        if isinstance(start_time, str):
            try:
                start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            except ValueError:
                pass
                
        if isinstance(end_time, str):
            try:
                end_time = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            except ValueError:
                pass
        
        return {
            'id': int(row[1]) if isinstance(row[1], str) else row[1],  # id
            'user_telegram_id': int(row[5]) if isinstance(row[5], str) else row[5],  # user_telegram_id
            'master_id': int(row[2]) if isinstance(row[2], str) else row[2],  # master_id
            'service_id': int(row[3]) if isinstance(row[3], str) else row[3],  # service_id
            'start_time': start_time,
            'end_time': end_time
        }