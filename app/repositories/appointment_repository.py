from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.appointment import Appointment
from app.repositories.base import BaseRepository


class AppointmentRepository(BaseRepository[Appointment]):
    """Репозиторий для работы с записями клиентов"""
    
    def __init__(self, db: Session):
        super().__init__(Appointment, db)
    
    def create(self, appointment_data: dict) -> Appointment:
        """Создать новую запись"""
        appointment = Appointment(**appointment_data)
        self.db.add(appointment)
        self.db.commit()
        self.db.refresh(appointment)
        return appointment
    
    def get_future_appointments_by_user(self, user_telegram_id: int) -> List[Appointment]:
        """Получить все предстоящие записи пользователя"""
        now = datetime.now()
        return self.db.query(Appointment).filter(
            and_(
                Appointment.user_telegram_id == user_telegram_id,
                Appointment.start_time > now
            )
        ).order_by(Appointment.start_time).all()
    
    def delete_by_event_id(self, event_id: str) -> bool:
        """Удалить запись по ID события в Google Календаре"""
        appointment = self.db.query(Appointment).filter(
            Appointment.google_event_id == event_id
        ).first()
        
        if appointment:
            self.db.delete(appointment)
            self.db.commit()
            return True
        return False
    
    def get_by_event_id(self, event_id: str) -> Optional[Appointment]:
        """Получить запись по ID события в Google Календаре"""
        return self.db.query(Appointment).filter(
            Appointment.google_event_id == event_id
        ).first()
    
    def get_next_appointment_by_user(self, user_telegram_id: int) -> Optional[Appointment]:
        """Получить ближайшую предстоящую запись пользователя"""
        now = datetime.now()
        return self.db.query(Appointment).filter(
            and_(
                Appointment.user_telegram_id == user_telegram_id,
                Appointment.start_time > now
            )
        ).order_by(Appointment.start_time).first()
    
    def check_duplicate_appointment(self, user_telegram_id: int, master_id: int, service_id: int, start_time: datetime) -> Optional[Appointment]:
        """Проверить наличие дублирующейся записи"""
        return self.db.query(Appointment).filter(
            and_(
                Appointment.user_telegram_id == user_telegram_id,
                Appointment.master_id == master_id,
                Appointment.service_id == service_id,
                Appointment.start_time == start_time
            )
        ).first()

    def delete(self, appointment: Appointment) -> bool:
        """Удалить конкретную запись (по объекту)."""
        if not appointment:
            return False
        self.db.delete(appointment)
        self.db.commit()
        return True

    def delete_by_id(self, appointment_id: int) -> bool:
        """Удалить запись по её первичному ключу."""
        appointment = self.get_by_id(appointment_id)
        if not appointment:
            return False
        self.db.delete(appointment)
        self.db.commit()
        return True

    def update(self, appointment_id: int, data: dict) -> Optional[Appointment]:
        """Обновить запись по её первичному ключу."""
        appointment = self.get_by_id(appointment_id)
        if not appointment:
            return None
        
        for key, value in data.items():
            if hasattr(appointment, key):
                setattr(appointment, key, value)
        
        self.db.commit()
        self.db.refresh(appointment)
        return appointment