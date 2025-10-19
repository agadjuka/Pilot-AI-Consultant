"""
Сервис для работы с календарем через базу данных.
Заменяет Google Calendar Service для автономной работы приложения.
"""
from datetime import datetime, timedelta, time, date
from typing import List, Dict, Optional, Tuple
from zoneinfo import ZoneInfo
import logging

from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.master_repository import MasterRepository
from app.repositories.schedule_repository import WorkScheduleRepository, ScheduleExceptionRepository

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
        master_repository: MasterRepository,
        work_schedule_repository: WorkScheduleRepository,
        schedule_exception_repository: ScheduleExceptionRepository
    ):
        """
        Инициализация сервиса календаря.
        
        Args:
            appointment_repository: Репозиторий для работы с записями
            master_repository: Репозиторий для работы с мастерами
            work_schedule_repository: Репозиторий для работы с графиками работы
            schedule_exception_repository: Репозиторий для работы с исключениями из графика
        """
        self.appointment_repository = appointment_repository
        self.master_repository = master_repository
        self.work_schedule_repository = work_schedule_repository
        self.schedule_exception_repository = schedule_exception_repository
    
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
            
            logger.info(f"✅ [DB CALENDAR] Запись создана с ID: {appointment['id']}")
            return appointment['id']
            
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
        Использует новые таблицы графиков работы мастеров для надежного определения рабочего времени.
        
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
                target_date = datetime.strptime(date, "%Y-%m-%d").date()
            except ValueError:
                raise Exception(f"Неверный формат даты: {date}. Ожидается формат YYYY-MM-DD")
            
            # Находим master_ids по именам мастеров
            master_ids = self._get_master_ids_by_names(master_names)
            if not master_ids:
                logger.warning(f"⚠️ [DB CALENDAR] Не найдено ни одного мастера из списка: {master_names}")
                return []
            
            # Получаем свободные слоты для каждого мастера
            all_free_slots = []
            for master_id in master_ids:
                master_slots = self._get_free_slots_for_master(target_date, duration_minutes, master_id)
                all_free_slots.extend(master_slots)
            
            # Убираем дубликаты и сортируем
            unique_slots = self._deduplicate_and_sort_slots(all_free_slots)
            
            logger.info(f"✅ [DB CALENDAR] Найдено свободных интервалов: {len(unique_slots)}")
            return unique_slots
            
        except Exception as e:
            logger.error(f"❌ [DB CALENDAR] Ошибка поиска свободных слотов: {str(e)}")
            raise Exception(f"Ошибка при поиске свободных слотов: {str(e)}")
    
    def _get_master_ids_by_names(self, master_names: List[str]) -> List[int]:
        """
        Находит ID мастеров по их именам.
        
        Args:
            master_names: Список имен мастеров
        
        Returns:
            List[int]: Список ID мастеров
        """
        master_ids = []
        if master_names:
            all_masters = self.master_repository.get_all()
            for master_name in master_names:
                master = next((m for m in all_masters if master_name.lower() in m['name'].lower()), None)
                if master:
                    master_ids.append(master['id'])
                    logger.info(f"✅ [DB CALENDAR] Найден мастер: {master_name} -> ID {master['id']}")
                else:
                    logger.warning(f"⚠️ [DB CALENDAR] Мастер не найден: {master_name}")
        return master_ids
    
    def _get_free_slots_for_master(
        self, 
        target_date: date, 
        duration_minutes: int, 
        master_id: int
    ) -> List[Dict[str, str]]:
        """
        Получает свободные слоты для конкретного мастера на указанную дату.
        
        Args:
            target_date: Целевая дата
            duration_minutes: Длительность услуги в минутах
            master_id: ID мастера
        
        Returns:
            List[Dict[str, str]]: Список свободных интервалов
        """
        # Шаг 1: Определение рабочего времени мастера на заданную дату
        work_time = self._get_master_work_time(target_date, master_id)
        if not work_time:
            logger.info(f"📅 [DB CALENDAR] Мастер {master_id} не работает {target_date}")
            return []
        
        start_time, end_time = work_time
        logger.info(f"⏰ [DB CALENDAR] Мастер {master_id} работает {target_date}: {start_time} - {end_time}")
        
        # Шаг 2: Генерация "идеальной" сетки слотов
        timeslot_grid = self._generate_timeslot_grid(start_time, end_time, target_date)
        logger.info(f"📊 [DB CALENDAR] Сгенерировано {len(timeslot_grid)} слотов для мастера {master_id}")
        
        # Шаг 3: Получение и "вычеркивание" занятых слотов
        occupied_slots = self._get_occupied_slots(target_date, master_id)
        free_slots = self._filter_occupied_slots(timeslot_grid, occupied_slots)
        logger.info(f"🆓 [DB CALENDAR] Осталось {len(free_slots)} свободных слотов для мастера {master_id}")
        
        # Шаг 4: Поиск непрерывных интервалов нужной длины
        contiguous_intervals = self._find_contiguous_intervals(free_slots, duration_minutes)
        logger.info(f"🔗 [DB CALENDAR] Найдено {len(contiguous_intervals)} интервалов для мастера {master_id}")
        
        return contiguous_intervals
    
    def _get_master_work_time(self, target_date: date, master_id: int) -> Optional[Tuple[time, time]]:
        """
        Определяет рабочее время мастера на заданную дату.
        
        Args:
            target_date: Целевая дата
            master_id: ID мастера
        
        Returns:
            Optional[Tuple[time, time]]: Кортеж (start_time, end_time) или None если мастер не работает
        """
        # Сначала проверяем исключения из графика
        exception = self.schedule_exception_repository.find_by_master_and_date(master_id, target_date)
        
        if exception:
            if exception['is_day_off']:
                logger.info(f"🚫 [DB CALENDAR] У мастера {master_id} выходной {target_date}")
                return None
            else:
                # Используем переопределенное время
                start_time = exception['start_time']
                end_time = exception['end_time']
                logger.info(f"📝 [DB CALENDAR] Мастер {master_id} имеет исключение {target_date}: {start_time} - {end_time}")
                return (start_time, end_time)
        
        # Если исключений нет, используем стандартный график
        day_of_week = target_date.weekday()  # 0=Понедельник, 6=Воскресенье
        schedule = self.work_schedule_repository.find_by_master_and_day(master_id, day_of_week)
        
        if not schedule:
            logger.info(f"📅 [DB CALENDAR] У мастера {master_id} нет графика на {target_date} (день недели {day_of_week})")
            return None
        
        start_time = schedule['start_time']
        end_time = schedule['end_time']
        logger.info(f"📋 [DB CALENDAR] Стандартный график мастера {master_id} на {target_date}: {start_time} - {end_time}")
        
        return (start_time, end_time)
    
    def _generate_timeslot_grid(self, start_time: time, end_time: time, target_date: date) -> List[time]:
        """
        Генерирует сетку 15-минутных слотов в рабочем времени мастера.
        
        Args:
            start_time: Время начала работы
            end_time: Время окончания работы
            target_date: Целевая дата
        
        Returns:
            List[time]: Список временных слотов
        """
        slots = []
        current_time = start_time
        
        # Если запрашивается сегодняшний день, учитываем текущее время
        moscow_tz = ZoneInfo('Europe/Moscow')
        now = datetime.now(moscow_tz)
        if target_date == now.date():
            # Минимальное время для записи = текущее время + 1 час
            min_booking_time = now + timedelta(hours=1)
            min_time = min_booking_time.time()
            # Округляем до ближайшего получаса в большую сторону
            if min_booking_time.minute > 30:
                min_time = time(min_booking_time.hour + 1, 0)
            elif min_booking_time.minute > 0:
                min_time = time(min_booking_time.hour, 30)
            else:
                min_time = time(min_booking_time.hour, 0)
            
            # Начинаем с минимального времени, если оно больше времени начала работы
            if min_time > start_time:
                current_time = min_time
        
        while current_time < end_time:
            slots.append(current_time)
            # Добавляем 15 минут
            current_datetime = datetime.combine(target_date, current_time)
            current_datetime += timedelta(minutes=15)
            current_time = current_datetime.time()
        
        return slots
    
    def _get_occupied_slots(self, target_date: date, master_id: int) -> List[Tuple[time, time]]:
        """
        Получает занятые временные интервалы мастера на указанную дату.
        
        Args:
            target_date: Целевая дата
            master_id: ID мастера
        
        Returns:
            List[Tuple[time, time]]: Список занятых интервалов (start_time, end_time)
        """
        moscow_tz = ZoneInfo('Europe/Moscow')
        day_start = datetime.combine(target_date, time.min).replace(tzinfo=moscow_tz)
        day_end = datetime.combine(target_date, time.max).replace(tzinfo=moscow_tz)
        
        # Получаем все записи мастера на эту дату
        occupied_appointments = self._get_appointments_for_master_on_date(master_id, day_start, day_end)
        
        occupied_slots = []
        for appointment in occupied_appointments:
            start_time = appointment.start_time.time()
            end_time = appointment.end_time.time()
            occupied_slots.append((start_time, end_time))
        
        return occupied_slots
    
    def _filter_occupied_slots(self, timeslot_grid: List[time], occupied_slots: List[Tuple[time, time]]) -> List[time]:
        """
        Фильтрует занятые слоты из сетки.
        
        Args:
            timeslot_grid: Сетка временных слотов
            occupied_slots: Список занятых интервалов
        
        Returns:
            List[time]: Список свободных слотов
        """
        free_slots = []
        
        for slot_time in timeslot_grid:
            is_occupied = False
            
            # Проверяем, не пересекается ли слот с каким-либо занятым интервалом
            for occupied_start, occupied_end in occupied_slots:
                # Слот считается занятым, если он попадает в занятый интервал
                if occupied_start <= slot_time < occupied_end:
                    is_occupied = True
                    break
            
            if not is_occupied:
                free_slots.append(slot_time)
        
        return free_slots
    
    def _find_contiguous_intervals(self, free_slots: List[time], duration_minutes: int) -> List[Dict[str, str]]:
        """
        Находит непрерывные интервалы достаточной длительности.
        
        Args:
            free_slots: Список свободных слотов
            duration_minutes: Минимальная длительность интервала
        
        Returns:
            List[Dict[str, str]]: Список интервалов в формате [{'start': '10:00', 'end': '11:30'}, ...]
        """
        if not free_slots:
            return []
        
        intervals = []
        current_start = free_slots[0]
        current_end = free_slots[0]
        
        for i in range(1, len(free_slots)):
            slot_time = free_slots[i]
            
            # Проверяем, является ли слот следующим по времени (через 15 минут)
            expected_time = datetime.combine(date.today(), current_end) + timedelta(minutes=15)
            if slot_time == expected_time.time():
                # Продолжаем текущий интервал
                current_end = slot_time
            else:
                # Завершаем текущий интервал и начинаем новый
                interval_duration = self._calculate_interval_duration(current_start, current_end)
                if interval_duration >= duration_minutes:
                    intervals.append({
                        'start': current_start.strftime('%H:%M'),
                        'end': (datetime.combine(date.today(), current_end) + timedelta(minutes=15)).strftime('%H:%M')
                    })
                
                current_start = slot_time
                current_end = slot_time
        
        # Обрабатываем последний интервал
        interval_duration = self._calculate_interval_duration(current_start, current_end)
        if interval_duration >= duration_minutes:
            intervals.append({
                'start': current_start.strftime('%H:%M'),
                'end': (datetime.combine(date.today(), current_end) + timedelta(minutes=15)).strftime('%H:%M')
            })
        
        return intervals
    
    def _calculate_interval_duration(self, start_time: time, end_time: time) -> int:
        """
        Вычисляет длительность интервала в минутах.
        
        Args:
            start_time: Время начала
            end_time: Время окончания
        
        Returns:
            int: Длительность в минутах
        """
        start_datetime = datetime.combine(date.today(), start_time)
        end_datetime = datetime.combine(date.today(), end_time)
        duration = end_datetime - start_datetime
        return int(duration.total_seconds() // 60) + 15  # +15 минут для последнего слота
    
    def _deduplicate_and_sort_slots(self, all_slots: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Убирает дубликаты и сортирует слоты.
        
        Args:
            all_slots: Список всех слотов
        
        Returns:
            List[Dict[str, str]]: Уникальные отсортированные слоты
        """
        # Убираем дубликаты
        unique_slots = []
        seen = set()
        
        for slot in all_slots:
            slot_key = f"{slot['start']}-{slot['end']}"
            if slot_key not in seen:
                seen.add(slot_key)
                unique_slots.append(slot)
        
        # Сортируем по времени начала
        unique_slots.sort(key=lambda x: x['start'])
        
        return unique_slots
    
    def _get_appointments_for_master_on_date(
        self,
        master_id: int,
        day_start: datetime,
        day_end: datetime
    ) -> List:
        """
        Получает все записи конкретного мастера на указанную дату.
        
        Args:
            master_id: ID мастера
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
                    self.appointment_repository.model.master_id == master_id,
                    self.appointment_repository.model.start_time >= day_start,
                    self.appointment_repository.model.start_time <= day_end
                )
            )
            .all()
        )
