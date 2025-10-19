"""
Сервис для работы с календарем через базу данных.
Заменяет Google Calendar Service для автономной работы приложения.
"""
from datetime import datetime, timedelta, time, date
from typing import List, Dict, Optional, Tuple, Any
from zoneinfo import ZoneInfo
import logging

from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.master_repository import MasterRepository
from app.repositories.master_schedule_repository import MasterScheduleRepository

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
        master_schedule_repository: MasterScheduleRepository
    ):
        """
        Инициализация сервиса календаря.
        
        Args:
            appointment_repository: Репозиторий для работы с записями
            master_repository: Репозиторий для работы с мастерами
            master_schedule_repository: Репозиторий для работы с графиками мастеров
        """
        self.appointment_repository = appointment_repository
        self.master_repository = master_repository
        self.master_schedule_repository = master_schedule_repository
    
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
        master_ids: List[int],
        tracer=None
    ) -> List[Dict[str, str]]:
        """
        Получает свободные временные интервалы на указанную дату для списка мастеров.
        Использует новый алгоритм "Таймлайн занятости" для эффективного поиска свободных слотов.
        
        Args:
            date: Дата в формате "YYYY-MM-DD"
            duration_minutes: Длительность услуги в минутах
            master_ids: Список ID мастеров для поиска
            tracer: Объект трассировщика для детального логирования
        
        Returns:
            List[Dict[str, str]]: Список свободных интервалов в формате [{'start': '10:15', 'end': '13:45'}, ...]
        
        Raises:
            Exception: Ошибка при работе с БД или неверный формат даты
        """
        try:
            logger.info(f"🔍 [TRACE] Поиск слотов: {date}, {duration_minutes}мин, мастера {master_ids}")
            
            # Логируем входные параметры
            if tracer:
                tracer.add_event("НАЧАЛО ПОИСКА СЛОТОВ", f"Дата: {date}, Длительность: {duration_minutes} мин, ID Мастеров: {master_ids}")
            
            # Парсим дату
            try:
                target_date = datetime.strptime(date, "%Y-%m-%d").date()
            except ValueError:
                raise Exception(f"Неверный формат даты: {date}. Ожидается формат YYYY-MM-DD")
            
            if not master_ids:
                logger.warning(f"⚠️ [DB CALENDAR] Передан пустой список мастеров")
                if tracer:
                    tracer.add_event("ПУСТОЙ СПИСОК МАСТЕРОВ", "Передан пустой список мастеров")
                return []
            
            # Шаг 1: Найти рабочие интервалы для каждого мастера
            work_intervals = self._get_work_intervals_for_masters(target_date, master_ids)
            
            # Логируем найденные рабочие графики
            if tracer:
                tracer.add_event("РАБОЧИЕ ГРАФИКИ НАЙДЕНЫ", f"Графики: {work_intervals}")
            
            if not work_intervals:
                logger.info(f"📅 [DB CALENDAR] Ни один из мастеров {master_ids} не работает {target_date}")
                if tracer:
                    tracer.add_event("МАСТЕРА НЕ РАБОТАЮТ", f"Дата: {target_date}, Мастера: {master_ids}")
                return []
            
            # Шаг 2: Найти все записи для этих мастеров на этот день
            appointments = self._get_appointments_for_masters_on_date(target_date, master_ids)
            
            # Логируем существующие записи
            if tracer:
                tracer.add_event("СУЩЕСТВУЮЩИЕ ЗАПИСИ", f"Найдено {len(appointments)} записей: {appointments}")
            
            # Шаг 3: Вычислить общие свободные интервалы через таймлайн
            free_intervals = self._calculate_free_intervals_timeline(target_date, work_intervals, appointments, tracer)
            
            # Логируем найденные свободные интервалы
            if tracer:
                tracer.add_event("НАЙДЕННЫЕ СВОБОДНЫЕ ИНТЕРВАЛЫ", f"{free_intervals}")
            
            # Шаг 4: Отфильтровать интервалы по длительности
            filtered_intervals = self._filter_intervals_by_duration(free_intervals, duration_minutes)
            
            # Логируем финальный результат
            if tracer:
                tracer.add_event("ФИНАЛЬНЫЙ РЕЗУЛЬТАТ (ПОСЛЕ ФИЛЬТРАЦИИ)", f"{filtered_intervals}")
            
            logger.info(f"✅ [TRACE] Результат: {len(filtered_intervals)} слотов")
            
            return filtered_intervals
            
        except Exception as e:
            logger.error(f"❌ [DB CALENDAR] Ошибка поиска свободных слотов: {str(e)}")
            if tracer:
                tracer.add_event("ОШИБКА ПОИСКА СЛОТОВ", f"Ошибка: {str(e)}")
            raise Exception(f"Ошибка при поиске свободных слотов: {str(e)}")
    
    def _get_work_intervals_for_masters(self, target_date: date, master_ids: List[int]) -> Dict[int, Tuple[time, time]]:
        """
        Получает рабочие интервалы для всех мастеров на указанную дату.
        
        Args:
            target_date: Целевая дата
            master_ids: Список ID мастеров
        
        Returns:
            Dict[int, Tuple[time, time]]: Словарь {master_id: (start_time, end_time)}
        """
        work_intervals = {}
        working_masters = []
        
        for master_id in master_ids:
            work_time = self._get_master_work_time(target_date, master_id)
            if work_time:
                start_time, end_time = work_time
                work_intervals[master_id] = (start_time, end_time)
                working_masters.append(f"{master_id}({start_time}-{end_time})")
        
        logger.info(f"👥 [TRACE] Рабочие мастера: {', '.join(working_masters) if working_masters else 'нет'}")
        return work_intervals
    
    def _get_appointments_for_masters_on_date(self, target_date: date, master_ids: List[int]) -> List[Dict[str, Any]]:
        """
        Получает все записи для списка мастеров на указанную дату.
        
        Args:
            target_date: Целевая дата
            master_ids: Список ID мастеров
        
        Returns:
            List[Dict[str, Any]]: Список записей
        """
        from app.core.database import execute_query
        
        # Формируем список ID для SQL запроса
        master_ids_str = ','.join(map(str, master_ids))
        
        # Получаем все записи для этих мастеров на эту дату
        query = f"""
            SELECT * FROM appointments 
            WHERE master_id IN ({master_ids_str})
            AND CAST(start_time AS Date) = CAST('{target_date}' AS Date)
            ORDER BY start_time
        """
        
        rows = execute_query(query)
        
        # Конвертируем строки в словари используя правильную конвертацию
        appointments = []
        for row in rows:
            # Используем конвертацию из репозитория
            appointment = self.appointment_repository._row_to_dict(row)
            appointments.append(appointment)
        
        logger.info(f"📅 [TRACE] Записи: {len(appointments)}шт")
        return appointments
    
    def _calculate_free_intervals_timeline(self, target_date: date, work_intervals: Dict[int, Tuple[time, time]], appointments: List[Dict[str, Any]], tracer=None) -> List[Dict[str, str]]:
        """
        Вычисляет свободные интервалы используя исправленный алгоритм "Сетка доступности".
        
        Алгоритм:
        1. Создает индивидуальные "сетки занятости" для каждого мастера
        2. Вычисляет "чистые" свободные интервалы для каждого мастера
        3. Находит интервалы, где свободен ХОТЯ БЫ ОДИН мастер
        
        Args:
            target_date: Целевая дата для поиска слотов
            work_intervals: Словарь рабочих интервалов мастеров
            appointments: Список записей
        
        Returns:
            List[Dict[str, str]]: Список свободных интервалов
        """
        logger.info(f"🔍 [GRID] Начинаем исправленный алгоритм 'Сетка доступности' для {len(work_intervals)} мастеров")
        
        # Шаг 1: Создаем индивидуальные "сетки занятости" для каждого мастера
        master_free_intervals = {}
        
        for master_id, (work_start, work_end) in work_intervals.items():
            logger.info(f"👤 [GRID] Обрабатываем мастера {master_id}: рабочий интервал {work_start}-{work_end}")
            
            # Получаем записи этого мастера
            master_appointments = [apt for apt in appointments if apt['master_id'] == master_id]
            
            # Создаем список занятых интервалов мастера
            busy_intervals = []
            for appointment in master_appointments:
                start_time = self._parse_appointment_time(appointment['start_time'], target_date)
                end_time = self._parse_appointment_time(appointment['end_time'], target_date)
                
                if start_time and end_time:
                    busy_intervals.append((start_time, end_time))
                    logger.info(f"  📅 [GRID] Занятость мастера {master_id}: {start_time.strftime('%H:%M')}-{end_time.strftime('%H:%M')}")
            
            # Вычисляем свободные интервалы для этого мастера
            master_free = self._calculate_master_free_intervals(
                target_date, work_start, work_end, busy_intervals
            )
            
            master_free_intervals[master_id] = master_free
            logger.info(f"  ✅ [GRID] Мастер {master_id} свободен: {len(master_free)} интервалов")
        
        # Логируем индивидуальные свободные интервалы
        if tracer:
            tracer.add_event("ИНДИВИДУАЛЬНЫЕ СВОБОДНЫЕ ИНТЕРВАЛЫ", f"{master_free_intervals}")
        
        # Шаг 2: Находим общие свободные интервалы (где свободен хотя бы один мастер)
        common_free_intervals = self._find_common_free_intervals(master_free_intervals)
        
        logger.info(f"🔗 [GRID] Найдено {len(common_free_intervals)} общих свободных интервалов")
        
        # Логируем финальный результат
        if tracer:
            tracer.add_event("ОБЩИЕ СВОБОДНЫЕ ИНТЕРВАЛЫ", f"{common_free_intervals}")
        
        return common_free_intervals
    
    def _find_common_free_intervals(self, master_free_intervals: Dict[int, List[Dict[str, str]]]) -> List[Dict[str, str]]:
        """
        Находит интервалы, где свободен хотя бы один мастер.
        
        Args:
            master_free_intervals: Словарь свободных интервалов для каждого мастера
        
        Returns:
            List[Dict[str, str]]: Список общих свободных интервалов
        """
        if not master_free_intervals:
            return []
        
        # Собираем все свободные интервалы всех мастеров
        all_intervals = []
        for master_id, intervals in master_free_intervals.items():
            for interval in intervals:
                all_intervals.append({
                    'start': interval['start'],
                    'end': interval['end'],
                    'master_id': master_id
                })
        
        if not all_intervals:
            return []
        
        # Сортируем по времени начала
        all_intervals.sort(key=lambda x: x['start'])
        
        logger.info(f"🔍 [GRID] Всего интервалов для объединения: {len(all_intervals)}")
        for interval in all_intervals:
            logger.info(f"  - {interval['start']}-{interval['end']} (мастер {interval['master_id']})")
        
        # Объединяем пересекающиеся интервалы
        merged_intervals = []
        current_start = all_intervals[0]['start']
        current_end = all_intervals[0]['end']
        
        for interval in all_intervals[1:]:
            # Если интервалы пересекаются или идут вплотную
            if interval['start'] <= current_end:
                # Расширяем текущий интервал
                current_end = max(current_end, interval['end'])
                logger.info(f"🔗 [GRID] Объединяем: {current_start}-{current_end}")
            else:
                # Добавляем завершенный интервал и начинаем новый
                merged_intervals.append({
                    'start': current_start,
                    'end': current_end
                })
                logger.info(f"✅ [GRID] Добавляем интервал: {current_start}-{current_end}")
                current_start = interval['start']
                current_end = interval['end']
        
        # Добавляем последний интервал
        merged_intervals.append({
            'start': current_start,
            'end': current_end
        })
        logger.info(f"✅ [GRID] Добавляем последний интервал: {current_start}-{current_end}")
        
        return merged_intervals
    
    def _parse_appointment_time(self, time_value: Any, target_date: date) -> Optional[datetime]:
        """
        Парсит время записи в datetime объект.
        
        Args:
            time_value: Время записи (datetime, time, str)
            target_date: Целевая дата
        
        Returns:
            Optional[datetime]: Распарсенное время или None при ошибке
        """
        try:
            if isinstance(time_value, datetime):
                return time_value
            elif hasattr(time_value, 'time'):
                return datetime.combine(target_date, time_value.time())
            elif isinstance(time_value, str):
                return datetime.fromisoformat(time_value.replace('Z', '+00:00'))
            else:
                logger.warning(f"⚠️ [GRID] Неизвестный тип времени: {type(time_value)}")
                return None
        except Exception as e:
            logger.warning(f"⚠️ [GRID] Ошибка парсинга времени {time_value}: {str(e)}")
            return None
    
    def _calculate_master_free_intervals(
        self, 
        target_date: date, 
        work_start: time, 
        work_end: time, 
        busy_intervals: List[Tuple[datetime, datetime]]
    ) -> List[Dict[str, str]]:
        """
        Вычисляет свободные интервалы для одного мастера.
        
        Args:
            target_date: Целевая дата
            work_start: Время начала работы
            work_end: Время окончания работы
            busy_intervals: Список занятых интервалов
        
        Returns:
            List[Dict[str, str]]: Список свободных интервалов мастера
        """
        # Сортируем занятые интервалы по времени начала
        busy_intervals.sort(key=lambda x: x[0])
        
        # Создаем рабочий интервал
        work_start_datetime = datetime.combine(target_date, work_start)
        work_end_datetime = datetime.combine(target_date, work_end)
        
        free_intervals = []
        current_start = work_start_datetime
        
        for busy_start, busy_end in busy_intervals:
            # Если есть свободное время до начала занятости
            if current_start < busy_start:
                free_intervals.append({
                    'start': current_start.strftime('%H:%M'),
                    'end': busy_start.strftime('%H:%M')
                })
            
            # Обновляем текущее время на конец занятости
            current_start = max(current_start, busy_end)
        
        # Если есть свободное время после последней занятости
        if current_start < work_end_datetime:
            free_intervals.append({
                'start': current_start.strftime('%H:%M'),
                'end': work_end_datetime.strftime('%H:%M')
            })
        
        return free_intervals
    
    def _merge_overlapping_intervals(self, intervals: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Объединяет пересекающиеся или идущие вплотную интервалы.
        
        Args:
            intervals: Список интервалов для объединения
        
        Returns:
            List[Dict[str, str]]: Объединенные интервалы
        """
        if not intervals:
            return []
        
        # Сортируем по времени начала
        intervals.sort(key=lambda x: x['start'])
        
        merged = []
        current_start = intervals[0]['start']
        current_end = intervals[0]['end']
        
        for interval in intervals[1:]:
            # Если интервалы пересекаются или идут вплотную
            if interval['start'] <= current_end:
                # Расширяем текущий интервал
                current_end = max(current_end, interval['end'])
            else:
                # Добавляем завершенный интервал и начинаем новый
                merged.append({
                    'start': current_start,
                    'end': current_end
                })
                current_start = interval['start']
                current_end = interval['end']
        
        # Добавляем последний интервал
        merged.append({
            'start': current_start,
            'end': current_end
        })
        
        return merged
    
    def _filter_intervals_by_duration(self, intervals: List[Dict[str, str]], duration_minutes: int) -> List[Dict[str, str]]:
        """
        Фильтрует интервалы по минимальной длительности.
        
        Args:
            intervals: Список интервалов
            duration_minutes: Минимальная длительность в минутах
        
        Returns:
            List[Dict[str, str]]: Отфильтрованные интервалы
        """
        filtered_intervals = []
        
        for interval in intervals:
            start_time = datetime.strptime(interval['start'], '%H:%M').time()
            end_time = datetime.strptime(interval['end'], '%H:%M').time()
            
            # Вычисляем длительность интервала
            start_datetime = datetime.combine(date.today(), start_time)
            end_datetime = datetime.combine(date.today(), end_time)
            duration = (end_datetime - start_datetime).total_seconds() / 60
            
            if duration >= duration_minutes:
                filtered_intervals.append(interval)
        
        logger.info(f"⏱️ [TRACE] Фильтр {duration_minutes}мин: {len(filtered_intervals)}шт")
        return filtered_intervals
    
    def _get_master_ids_by_names(self, master_names: List[str]) -> List[int]:
        """
        Находит ID мастеров по их именам (для обратной совместимости).
        
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
    
    def _get_master_work_time(self, target_date: date, master_id: int) -> Optional[Tuple[time, time]]:
        """
        Получает рабочее время мастера на заданную дату из таблицы master_schedules.
        
        Args:
            target_date: Целевая дата
            master_id: ID мастера
        
        Returns:
            Optional[Tuple[time, time]]: Кортеж (start_time, end_time) или None если мастер не работает
        """
        try:
            # Получаем график работы мастера на конкретную дату из БД
            schedule = self.master_schedule_repository.find_by_master_and_date(master_id, target_date)
            
            if not schedule:
                logger.info(f"🚫 [DB CALENDAR] Мастер {master_id} не работает {target_date} - график не найден")
                return None
            
            # Извлекаем время начала и окончания работы
            start_time_str = schedule['start_time']
            end_time_str = schedule['end_time']
            
            # Парсим строки времени в объекты time
            # Поддерживаем форматы HH:MM и HH:MM:SS
            try:
                start_time = datetime.strptime(start_time_str, '%H:%M').time()
            except ValueError:
                # Если не удалось распарсить в формате HH:MM, пробуем HH:MM:SS
                start_time = datetime.strptime(start_time_str, '%H:%M:%S').time()
            
            try:
                end_time = datetime.strptime(end_time_str, '%H:%M').time()
            except ValueError:
                # Если не удалось распарсить в формате HH:MM, пробуем HH:MM:SS
                end_time = datetime.strptime(end_time_str, '%H:%M:%S').time()
            
            logger.info(f"⏰ [DB CALENDAR] Рабочие часы мастера {master_id} на {target_date}: {start_time} - {end_time}")
            return (start_time, end_time)
            
        except Exception as e:
            logger.error(f"❌ [DB CALENDAR] Ошибка получения графика мастера {master_id} на {target_date}: {str(e)}")
            return None
    
