from sqlalchemy import Column, Integer, Date, Time, ForeignKey
from app.core.database import Base


class MasterSchedule(Base):
    """Модель для хранения графиков работы мастеров по конкретным датам"""
    __tablename__ = "master_schedules"
    
    id = Column(Integer, primary_key=True)
    master_id = Column(Integer, ForeignKey("masters.id"), nullable=False)
    date = Column(Date, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
