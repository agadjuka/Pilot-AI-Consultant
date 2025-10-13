"""
Сервис для работы с Google Calendar API.
Используется единый календарь для всех мастеров.
"""
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from zoneinfo import ZoneInfo
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from app.core.config import settings


class GoogleCalendarService:
    """
    Сервис для работы с Google Calendar API.
    Использует аутентификацию через сервисный аккаунт.
    """
    
    # Области доступа для Google Calendar API
    SCOPES = ['https://www.googleapis.com/auth/calendar']
    
    def __init__(self):
        """
        Инициализация сервиса Google Calendar.
        Создает клиент для работы с Calendar API v3.
        """
        self.calendar_id = settings.GOOGLE_CALENDAR_ID
        self.service = self._authenticate()
    
    def _authenticate(self):
        """
        Аутентификация через сервисный аккаунт.
        
        Returns:
            Resource: Объект сервиса Google Calendar API
        """
        try:
            credentials = service_account.Credentials.from_service_account_file(
                settings.GOOGLE_APPLICATION_CREDENTIALS,
                scopes=self.SCOPES
            )
            service = build('calendar', 'v3', credentials=credentials)
            return service
        except Exception as e:
            raise Exception(f"Ошибка аутентификации Google Calendar: {str(e)}")
    
    def create_event(
        self,
        summary: str,
        start_datetime: datetime,
        end_datetime: datetime,
        description: Optional[str] = None,
        location: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Создание нового события в календаре.
        
        Args:
            summary: Название события
            start_datetime: Дата и время начала
            end_datetime: Дата и время окончания
            description: Описание события (опционально)
            location: Место проведения (опционально)
        
        Returns:
            Dict: Созданное событие
        
        Raises:
            HttpError: Ошибка при работе с API
        """
        # Формируем время в формате ISO с московским offset +03:00
        # Это гарантирует, что Google Calendar сохранит именно это время
        if start_datetime.tzinfo is not None:
            # Если есть timezone, форматируем с offset
            start_str = start_datetime.strftime('%Y-%m-%dT%H:%M:%S+03:00')
            end_str = end_datetime.strftime('%Y-%m-%dT%H:%M:%S+03:00')
        else:
            # Если нет timezone, добавляем московский offset
            start_str = start_datetime.strftime('%Y-%m-%dT%H:%M:%S') + '+03:00'
            end_str = end_datetime.strftime('%Y-%m-%dT%H:%M:%S') + '+03:00'
        
        event = {
            'summary': summary,
            'description': description,
            'location': location,
            'start': {
                'dateTime': start_str,
            },
            'end': {
                'dateTime': end_str,
            },
        }
        
        try:
            created_event = self.service.events().insert(
                calendarId=self.calendar_id,
                body=event
            ).execute()
            return created_event
        except HttpError as error:
            raise Exception(f"Ошибка при создании события: {error}")
    
    def get_events(
        self,
        time_min: Optional[datetime] = None,
        time_max: Optional[datetime] = None,
        max_results: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Получение списка событий из календаря.
        
        Args:
            time_min: Начало временного диапазона (опционально)
            time_max: Конец временного диапазона (опционально)
            max_results: Максимальное количество результатов
        
        Returns:
            List[Dict]: Список событий
        
        Raises:
            HttpError: Ошибка при работе с API
        """
        try:
            params = {
                'calendarId': self.calendar_id,
                'maxResults': max_results,
                'singleEvents': True,
                'orderBy': 'startTime'
            }
            
            if time_min:
                # Если datetime имеет timezone, используем isoformat() как есть
                # Иначе считаем его UTC и добавляем 'Z'
                if time_min.tzinfo is not None:
                    params['timeMin'] = time_min.isoformat()
                else:
                    params['timeMin'] = time_min.isoformat() + 'Z'
            
            if time_max:
                # Аналогично для timeMax
                if time_max.tzinfo is not None:
                    params['timeMax'] = time_max.isoformat()
                else:
                    params['timeMax'] = time_max.isoformat() + 'Z'
            
            events_result = self.service.events().list(**params).execute()
            events = events_result.get('items', [])
            return events
        except HttpError as error:
            raise Exception(f"Ошибка при получении событий: {error}")
    
    def delete_event(self, event_id: str) -> None:
        """
        Удаление события из календаря.
        
        Args:
            event_id: ID события для удаления
        
        Raises:
            HttpError: Ошибка при работе с API
        """
        try:
            self.service.events().delete(
                calendarId=self.calendar_id,
                eventId=event_id
            ).execute()
        except HttpError as error:
            raise Exception(f"Ошибка при удалении события: {error}")
    
    def clear_calendar(
        self,
        time_min: Optional[datetime] = None,
        time_max: Optional[datetime] = None
    ) -> int:
        """
        Очистка календаря - удаление всех событий в указанном диапазоне.
        
        Args:
            time_min: Начало временного диапазона (опционально)
            time_max: Конец временного диапазона (опционально)
        
        Returns:
            int: Количество удаленных событий
        """
        events = self.get_events(time_min=time_min, time_max=time_max)
        deleted_count = 0
        
        for event in events:
            try:
                self.delete_event(event['id'])
                deleted_count += 1
            except Exception as e:
                print(f"Не удалось удалить событие {event.get('id')}: {str(e)}")
        
        return deleted_count
    
    def update_event(
        self,
        event_id: str,
        summary: Optional[str] = None,
        start_datetime: Optional[datetime] = None,
        end_datetime: Optional[datetime] = None,
        description: Optional[str] = None,
        location: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Обновление существующего события.
        
        Args:
            event_id: ID события для обновления
            summary: Новое название события (опционально)
            start_datetime: Новая дата и время начала (опционально)
            end_datetime: Новая дата и время окончания (опционально)
            description: Новое описание (опционально)
            location: Новое место проведения (опционально)
        
        Returns:
            Dict: Обновленное событие
        
        Raises:
            HttpError: Ошибка при работе с API
        """
        try:
            # Получаем текущее событие
            event = self.service.events().get(
                calendarId=self.calendar_id,
                eventId=event_id
            ).execute()
            
            # Обновляем поля
            if summary is not None:
                event['summary'] = summary
            if description is not None:
                event['description'] = description
            if location is not None:
                event['location'] = location
            if start_datetime is not None:
                event['start'] = {
                    'dateTime': start_datetime.isoformat(),
                    'timeZone': 'Europe/Moscow',
                }
            if end_datetime is not None:
                event['end'] = {
                    'dateTime': end_datetime.isoformat(),
                    'timeZone': 'Europe/Moscow',
                }
            
            # Отправляем обновленное событие
            updated_event = self.service.events().update(
                calendarId=self.calendar_id,
                eventId=event_id,
                body=event
            ).execute()
            
            return updated_event
        except HttpError as error:
            raise Exception(f"Ошибка при обновлении события: {error}")
    
    def get_free_slots(self, master_name: str, date: str, duration_minutes: int) -> List[str]:
        """
        Получает свободные временные слоты для мастера на указанную дату.
        Ищет непрерывные интервалы, достаточные для выполнения услуги заданной длительности.
        
        Args:
            master_name: Имя мастера
            date: Дата в формате "YYYY-MM-DD"
            duration_minutes: Длительность услуги в минутах
        
        Returns:
            List[str]: Список начальных времен доступных слотов в формате "HH:MM"
        
        Raises:
            Exception: Ошибка при работе с API или неверный формат даты
        """
        try:
            # Парсим дату (просто как есть, без timezone для начала дня)
            target_date = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise Exception(f"Неверный формат даты: {date}. Ожидается формат YYYY-MM-DD")
        
        # Определяем рабочее время салона (10:00 - 20:00)
        WORK_START_HOUR = 10
        WORK_END_HOUR = 20
        SLOT_DURATION_MINUTES = 30  # Шаг слотов - 30 минут
        
        # Формируем временные рамки для поиска
        # Добавляем московский timezone для корректного запроса к API
        moscow_tz = ZoneInfo('Europe/Moscow')
        day_start = target_date.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=moscow_tz)
        day_end = target_date.replace(hour=23, minute=59, second=59, microsecond=999999, tzinfo=moscow_tz)
        
        # Получаем все события за этот день
        events = self.get_events(time_min=day_start, time_max=day_end)
        
        # Фильтруем события для конкретного мастера
        master_events = []
        master_prefix = f"Запись: {master_name}"
        
        print(f"\n🔍 Поиск событий для мастера '{master_name}' на {date}")
        print(f"   Всего событий в календаре за этот день: {len(events)}")
        
        for event in events:
            summary = event.get('summary', '')
            if summary.startswith(master_prefix):
                # Извлекаем время начала и окончания события
                start_str = event.get('start', {}).get('dateTime')
                end_str = event.get('end', {}).get('dateTime')
                
                if start_str and end_str:
                    print(f"   📅 Исходная строка из API: {start_str}")
                    
                    # Парсим дату и время без timezone - просто берём как строку
                    # Формат: "2025-10-14T16:00:00+03:00"
                    # Нам нужна только дата и время без timezone
                    start_time = datetime.fromisoformat(start_str[:19])  # Берём только "2025-10-14T16:00:00"
                    end_time = datetime.fromisoformat(end_str[:19])
                    
                    # Добавляем московский timezone для корректного сравнения
                    moscow_tz = ZoneInfo('Europe/Moscow')
                    start_time = start_time.replace(tzinfo=moscow_tz)
                    end_time = end_time.replace(tzinfo=moscow_tz)
                    
                    master_events.append({
                        'start': start_time,
                        'end': end_time
                    })
                    print(f"   ✓ Найдена запись: {start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')}")
        
        print(f"   Записей мастера {master_name}: {len(master_events)}")
        
        # Вычисляем свободные слоты
        free_slots = []
        
        # Начинаем с начала рабочего дня (добавляем timezone для сравнения)
        moscow_tz = ZoneInfo('Europe/Moscow')
        current_slot = target_date.replace(
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
        
        print(f"\n⏰ Вычисление свободных слотов:")
        print(f"   Рабочее время: {WORK_START_HOUR}:00 - {WORK_END_HOUR}:00")
        print(f"   Шаг слотов: {SLOT_DURATION_MINUTES} минут")
        print(f"   Длительность услуги: {duration_minutes} минут")
        
        # Проходим по всем слотам рабочего дня
        while current_slot < work_end:
            # Проверяем, достаточно ли времени до конца рабочего дня
            required_end_time = current_slot + timedelta(minutes=duration_minutes)
            if required_end_time > work_end:
                break  # Нет смысла проверять дальше, услуга не влезет
            
            # Проверяем, свободен ли весь интервал для услуги
            is_interval_free = True
            for event in master_events:
                # Интервал занят, если он пересекается с событием
                # Услуга требует интервал [current_slot, required_end_time)
                if (current_slot < event['end'] and required_end_time > event['start']):
                    is_interval_free = False
                    break
            
            # Если интервал свободен, добавляем начальное время в список
            if is_interval_free:
                free_slots.append(current_slot.strftime("%H:%M"))
            
            # Переходим к следующему слоту (шаг 30 минут)
            current_slot = current_slot + timedelta(minutes=SLOT_DURATION_MINUTES)
        
        print(f"   ✅ Найдено свободных слотов: {len(free_slots)}")
        if free_slots:
            print(f"   Первые слоты: {', '.join(free_slots[:5])}")
        
        return free_slots

