"""
Сервис для работы с календарем через базу данных.
Заменяет Google Calendar Service для автономной работы приложения.
"""
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from zoneinfo import ZoneInfo
import logging

from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.master_repository import MasterRepository

# Получаем логгер для этого модуля
logger = logging.getLogger(__name__)


class DBCalendarService:
    """
    Сервис для работы с календарем через базу данных.
    Использует AppointmentRepository и MasterRepository для управления записями.
    """
    
    def __init__(
        self,
        appointment_repository: AppointmentRepository,
        master_repository: MasterRepository
    ):
        """
        Инициализация сервиса календаря.
        
        Args:
            appointment_repository: Репозиторий для работы с записями
            master_repository: Репозиторий для работы с мастерами
        """
        self.appointment_repository = appointment_repository
        self.master_repository = master_repository
    
    def create_event(
        self,
        master_id: int,
        service_id: int,
        user_telegram_id: int,
        start_time: datetime,
        end_time: datetime,
        description: str
    ) -> int:
        """
        Создание записи в календаре.
        
        Args:
            master_id: ID мастера
            service_id: ID услуги
            user_telegram_id: ID пользователя в Telegram
            start_time: Время начала записи
            end_time: Время окончания записи
            description: Описание записи
        
        Returns:
            int: ID созданной записи в БД
        
        Raises:
            Exception: Ошибка при создании записи
        """
        try:
            logger.info(f"📝 [DB CALENDAR] Создание записи: master_id={master_id}, service_id={service_id}, user_id={user_telegram_id}, start={start_time}, end={end_time}")
            
            # Создаем данные для записи
            appointment_data = {
                'user_telegram_id': user_telegram_id,
                'master_id': master_id,
                'service_id': service_id,
                'start_time': start_time,
                'end_time': end_time
            }
            
            # Создаем запись через репозиторий
            appointment = self.appointment_repository.create(appointment_data)
            
            logger.info(f"✅ [DB CALENDAR] Запись создана с ID: {appointment.id}")
            return appointment.id
            
        except Exception as e:
            logger.error(f"❌ [DB CALENDAR] Ошибка создания записи: {str(e)}")
            raise Exception(f"Ошибка при создании записи: {str(e)}")
    
    def delete_event(self, appointment_id: int) -> None:
        """
        Удаление записи из календаря.
        
        Args:
            appointment_id: ID записи для удаления
        
        Raises:
            Exception: Ошибка при удалении записи
        """
        try:
            logger.info(f"🗑️ [DB CALENDAR] Удаление записи: appointment_id={appointment_id}")
            
            # Удаляем запись через репозиторий
            deleted = self.appointment_repository.delete_by_id(appointment_id)
            
            if not deleted:
                raise Exception(f"Запись с ID {appointment_id} не найдена")
            
            logger.info(f"✅ [DB CALENDAR] Запись удалена: appointment_id={appointment_id}")
            
        except Exception as e:
            logger.error(f"❌ [DB CALENDAR] Ошибка удаления записи: {str(e)}")
            raise Exception(f"Ошибка при удалении записи: {str(e)}")
    
    def update_event(
        self,
        appointment_id: int,
        new_start_time: datetime,
        new_end_time: datetime
    ) -> None:
        """
        Обновление времени записи.
        
        Args:
            appointment_id: ID записи для обновления
            new_start_time: Новое время начала
            new_end_time: Новое время окончания
        
        Raises:
            Exception: Ошибка при обновлении записи
        """
        try:
            logger.info(f"📅 [DB CALENDAR] Обновление записи: appointment_id={appointment_id}, new_start={new_start_time}, new_end={new_end_time}")
            
            # Подготавливаем данные для обновления
            update_data = {
                'start_time': new_start_time,
                'end_time': new_end_time
            }
            
            # Обновляем запись через репозиторий
            updated_appointment = self.appointment_repository.update(appointment_id, update_data)
            
            if not updated_appointment:
                raise Exception(f"Запись с ID {appointment_id} не найдена")
            
            logger.info(f"✅ [DB CALENDAR] Запись обновлена: appointment_id={appointment_id}")
            
        except Exception as e:
            logger.error(f"❌ [DB CALENDAR] Ошибка обновления записи: {str(e)}")
            raise Exception(f"Ошибка при обновлении записи: {str(e)}")
    
    def get_free_slots(
        self,
        date: str,
        duration_minutes: int,
        master_names: List[str]
    ) -> List[Dict[str, str]]:
        """
        Получает свободные временные интервалы на указанную дату.
        Ищет непрерывные интервалы, достаточные для выполнения услуги заданной длительности.
        
        Args:
            date: Дата в формате "YYYY-MM-DD"
            duration_minutes: Длительность услуги в минутах
            master_names: Список имен мастеров для поиска
        
        Returns:
            List[Dict[str, str]]: Список свободных интервалов в формате [{'start': '10:15', 'end': '13:45'}, ...]
        
        Raises:
            Exception: Ошибка при работе с БД или неверный формат даты
        """
        try:
            logger.info(f"🔍 [DB CALENDAR] Поиск свободных слотов: date={date}, duration={duration_minutes} мин, masters={master_names}")
            
            # Парсим дату
            try:
                target_date = datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                raise Exception(f"Неверный формат даты: {date}. Ожидается формат YYYY-MM-DD")
            
            # Определяем рабочее время салона (10:00 - 20:00)
            WORK_START_HOUR = 10
            WORK_END_HOUR = 20
            
            # Находим master_ids по именам мастеров
            master_ids = []
            if master_names:
                all_masters = self.master_repository.get_all()
                for master_name in master_names:
                    master = next((m for m in all_masters if master_name.lower() in m.name.lower()), None)
                    if master:
                        master_ids.append(master.id)
                        logger.info(f"✅ [DB CALENDAR] Найден мастер: {master_name} -> ID {master.id}")
                    else:
                        logger.warning(f"⚠️ [DB CALENDAR] Мастер не найден: {master_name}")
            
            if not master_ids:
                logger.warning(f"⚠️ [DB CALENDAR] Не найдено ни одного мастера из списка: {master_names}")
                return []
            
            # Получаем все записи для этих мастеров на указанную дату
            moscow_tz = ZoneInfo('Europe/Moscow')
            day_start = target_date.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=moscow_tz)
            day_end = target_date.replace(hour=23, minute=59, second=59, microsecond=999999, tzinfo=moscow_tz)
            
            # Получаем все записи за день для указанных мастеров
            occupied_appointments = self._get_appointments_for_masters_on_date(master_ids, day_start, day_end)
            
            logger.info(f"📋 [DB CALENDAR] Найдено занятых записей: {len(occupied_appointments)}")
            
            # Создаем список всех занятых блоков
            occupied_blocks = []
            for appointment in occupied_appointments:
                occupied_blocks.append({
                    'start': appointment.start_time,
                    'end': appointment.end_time
                })
            
            # Сортируем занятые блоки по времени начала
            occupied_blocks.sort(key=lambda x: x['start'])
            
            # Определяем границы рабочего дня
            work_start = target_date.replace(
                hour=WORK_START_HOUR, 
                minute=0, 
                second=0, 
                microsecond=0,
                tzinfo=moscow_tz
            )
            work_end = target_date.replace(
                hour=WORK_END_HOUR, 
                minute=0, 
                second=0, 
                microsecond=0,
                tzinfo=moscow_tz
            )
            
            # Если запрашивается сегодняшний день, учитываем текущее время + буфер 1 час
            now = datetime.now(moscow_tz)
            if target_date.date() == now.date():
                # Минимальное время для записи = текущее время + 1 час
                min_booking_time = now + timedelta(hours=1)
                # Округляем до ближайшего получаса в большую сторону
                min_hour = min_booking_time.hour
                min_minute = 30 if min_booking_time.minute > 0 else 0
                if min_booking_time.minute > 30:
                    min_hour += 1
                    min_minute = 0
                
                # Обновляем начало рабочего дня, если нужно
                adjusted_work_start = target_date.replace(
                    hour=min_hour,
                    minute=min_minute,
                    second=0,
                    microsecond=0,
                    tzinfo=moscow_tz
                )
                
                if adjusted_work_start > work_start:
                    work_start = adjusted_work_start
            
            # Находим свободные интервалы с учетом количества мастеров (хотя бы один свободен)
            capacity = len(master_ids)
            
            # Строим события изменения занятости
            timeline: List[tuple[datetime, int]] = []
            for b in occupied_blocks:
                # Ограничиваем рамками рабочего дня
                s = max(b['start'], work_start)
                e = min(b['end'], work_end)
                if s < e:
                    timeline.append((s, +1))
                    timeline.append((e, -1))
            
            # Добавляем явные границы, чтобы закрыть интервалы
            timeline.append((work_start, 0))
            timeline.append((work_end, 0))
            timeline.sort(key=lambda x: (x[0], -x[1]))

            # Проходим по таймлайну, собирая интервалы, где занятость < capacity
            free_segments: List[tuple[datetime, datetime]] = []
            busy_count = 0
            segment_start: Optional[datetime] = None
            prev_time: Optional[datetime] = None
            
            for t, delta in timeline:
                if prev_time is not None and prev_time < t:
                    # Интервал [prev_time, t)
                    if busy_count < capacity:
                        # Это свободный сегмент
                        if segment_start is None:
                            segment_start = prev_time
                    else:
                        # Был занятый период, закрываем свободный сегмент если открыт
                        if segment_start is not None and segment_start < prev_time:
                            free_segments.append((segment_start, prev_time))
                            segment_start = None
                
                # Обновляем занятость на текущей точке
                busy_count += delta
                prev_time = t
            
            # Закрываем последний свободный сегмент
            if segment_start is not None and segment_start < work_end:
                free_segments.append((segment_start, work_end))

            # Фильтруем по длительности
            free_intervals: List[Dict[str, str]] = []
            for s, e in free_segments:
                minutes = int((e - s).total_seconds() // 60)
                if minutes >= duration_minutes:
                    free_intervals.append({'start': s.strftime('%H:%M'), 'end': e.strftime('%H:%M')})
            
            logger.info(f"✅ [DB CALENDAR] Найдено свободных интервалов: {len(free_intervals)}")
            return free_intervals
            
        except Exception as e:
            logger.error(f"❌ [DB CALENDAR] Ошибка поиска свободных слотов: {str(e)}")
            raise Exception(f"Ошибка при поиске свободных слотов: {str(e)}")
    
    def _get_appointments_for_masters_on_date(
        self,
        master_ids: List[int],
        day_start: datetime,
        day_end: datetime
    ) -> List:
        """
        Получает все записи для указанных мастеров на указанную дату.
        
        Args:
            master_ids: Список ID мастеров
            day_start: Начало дня
            day_end: Конец дня
        
        Returns:
            List: Список записей
        """
        from sqlalchemy import and_
        
        return (
            self.appointment_repository.db.query(self.appointment_repository.model)
            .filter(
                and_(
                    self.appointment_repository.model.master_id.in_(master_ids),
                    self.appointment_repository.model.start_time >= day_start,
                    self.appointment_repository.model.start_time <= day_end
                )
            )
            .all()
        )
