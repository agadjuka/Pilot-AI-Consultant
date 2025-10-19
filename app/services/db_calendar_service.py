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
        Вычисляет свободные интервалы используя алгоритм "Таймлайн занятости".
        
        Args:
            target_date: Целевая дата для поиска слотов
            work_intervals: Словарь рабочих интервалов мастеров
            appointments: Список записей
        
        Returns:
            List[Dict[str, str]]: Список свободных интервалов
        """
        timeline = []
        
        # Добавляем события начала и окончания работы мастеров
        for master_id, (start_time, end_time) in work_intervals.items():
            # Преобразуем time в datetime, объединяя с целевой датой
            start_datetime = datetime.combine(target_date, start_time)
            end_datetime = datetime.combine(target_date, end_time)
            
            timeline.append((start_datetime, 1, 'work_start', master_id))  # +1 свободен
            timeline.append((end_datetime, -1, 'work_end', master_id))     # -1 ушел с работы
        
        # Добавляем события записей
        for appointment in appointments:
            start_time = appointment['start_time']
            end_time = appointment['end_time']
            
            # Обрабатываем время начала записи
            if isinstance(start_time, datetime):
                start_datetime = start_time
            elif hasattr(start_time, 'time'):
                start_datetime = datetime.combine(target_date, start_time.time())
            elif isinstance(start_time, str):
                # Если это строка, парсим её
                try:
                    start_datetime = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                except:
                    # Если не удается парсить, пропускаем эту запись
                    logger.warning(f"⚠️ [DB CALENDAR] Не удается парсить время начала записи: {start_time}")
                    continue
            else:
                logger.warning(f"⚠️ [DB CALENDAR] Неизвестный тип времени начала: {type(start_time)}")
                continue
                
            # Обрабатываем время окончания записи
            if isinstance(end_time, datetime):
                end_datetime = end_time
            elif hasattr(end_time, 'time'):
                end_datetime = datetime.combine(target_date, end_time.time())
            elif isinstance(end_time, str):
                # Если это строка, парсим её
                try:
                    end_datetime = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
                except:
                    # Если не удается парсить, пропускаем эту запись
                    logger.warning(f"⚠️ [DB CALENDAR] Не удается парсить время окончания записи: {end_time}")
                    continue
            else:
                logger.warning(f"⚠️ [DB CALENDAR] Неизвестный тип времени окончания: {type(end_time)}")
                continue
            
            # Проверяем, что время корректно обработано
            if isinstance(start_datetime, datetime) and isinstance(end_datetime, datetime):
                timeline.append((start_datetime, -1, 'appointment_start', appointment['master_id']))  # -1 занят
                timeline.append((end_datetime, 1, 'appointment_end', appointment['master_id']))       # +1 освободился
            else:
                logger.warning(f"⚠️ [DB CALENDAR] Пропускаем запись с некорректным временем: start={type(start_datetime)}, end={type(end_datetime)}")
        
        # Логируем сырой таймлайн до сортировки
        if tracer:
            tracer.add_event("СЫРОЙ ТАЙМЛАЙН (ДО СОРТИРОВКИ)", f"{timeline}")
        
        # Сортируем таймлайн по времени
        timeline.sort(key=lambda x: x[0])
        
        # Отладочная информация
        logger.info(f"🔍 [DEBUG] Таймлайн событий:")
        for timestamp, delta, event_type, master_id in timeline:
            logger.info(f"  {timestamp.strftime('%H:%M')} | {event_type} | Мастер {master_id} | Delta: {delta}")
        
        # Проходим по таймлайну и находим свободные интервалы
        free_intervals = []
        available_masters = set()  # Множество доступных мастеров
        current_start = None
        
        for timestamp, delta, event_type, master_id in timeline:
            if event_type in ['work_start', 'appointment_end']:
                # Мастер становится доступным
                available_masters.add(master_id)
            elif event_type in ['work_end', 'appointment_start']:
                # Мастер становится недоступным
                available_masters.discard(master_id)
            
            # Проверяем, есть ли доступные мастера
            has_available_masters = len(available_masters) > 0
            
            if has_available_masters and current_start is None:
                # Начинается свободный интервал
                current_start = timestamp
            elif not has_available_masters and current_start is not None:
                # Заканчивается свободный интервал
                free_intervals.append({
                    'start': current_start.strftime('%H:%M'),
                    'end': timestamp.strftime('%H:%M')
                })
                current_start = None
        
        # Если интервал не закрылся до конца дня
        if current_start is not None:
            # Находим максимальное время окончания работы среди всех мастеров
            max_end_time = max(end_time for _, end_time in work_intervals.values())
            max_end_datetime = datetime.combine(target_date, max_end_time)
            free_intervals.append({
                'start': current_start.strftime('%H:%M'),
                'end': max_end_datetime.strftime('%H:%M')
            })
        
        logger.info(f"🔗 [TRACE] Свободные интервалы: {len(free_intervals)}шт")
        return free_intervals
    
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
        Определяет рабочее время мастера на заданную дату.
        Использует фиксированные рабочие часы: 9:00-18:00, воскресенье - выходной.
        
        Args:
            target_date: Целевая дата
            master_id: ID мастера
        
        Returns:
            Optional[Tuple[time, time]]: Кортеж (start_time, end_time) или None если мастер не работает
        """
        # Проверяем, не выходной ли это
        day_of_week = target_date.weekday()
        if day_of_week == 6:  # Воскресенье
            logger.info(f"🚫 [DB CALENDAR] Воскресенье - выходной для мастера {master_id}")
            return None
        
        # Фиксированные рабочие часы: 9:00 - 18:00
        start_time = time(9, 0)
        end_time = time(18, 0)
        
        logger.info(f"⏰ [DB CALENDAR] Рабочие часы мастера {master_id} на {target_date}: {start_time} - {end_time}")
        return (start_time, end_time)
    
