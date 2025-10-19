from sqlalchemy import Column, Integer, Time, Date, Boolean, ForeignKey
from app.core.database import Base


class WorkSchedule(Base):
    """Модель для хранения графиков работы мастеров по дням недели"""
    __tablename__ = "work_schedules"
    
    id = Column(Integer, primary_key=True)
    master_id = Column(Integer, ForeignKey("masters.id"), nullable=False)
    day_of_week = Column(Integer, nullable=False)  # 0=Понедельник, 1=Вторник...
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)


class ScheduleException(Base):
    """Модель для хранения исключений из стандартного графика работы"""
    __tablename__ = "schedule_exceptions"
    
    id = Column(Integer, primary_key=True)
    master_id = Column(Integer, ForeignKey("masters.id"), nullable=False)
    date = Column(Date, nullable=False)
    is_day_off = Column(Boolean, default=False)
    start_time = Column(Time, nullable=True)  # Переопределяет стандартный график
    end_time = Column(Time, nullable=True)    # Переопределяет стандартный график
