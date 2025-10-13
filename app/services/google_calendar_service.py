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
        master_name: str,
        service_name: str,
        start_time_iso: str,
        end_time_iso: str
    ) -> bool:
        """
        Создание записи в календаре для мастера и услуги.
        
        Args:
            master_name: Имя мастера
            service_name: Название услуги
            start_time_iso: Время начала в формате ISO 8601 (например, '2025-10-27T10:00:00')
            end_time_iso: Время окончания в формате ISO 8601 (например, '2025-10-27T11:00:00')
        
        Returns:
            bool: True в случае успешного создания записи
        
        Raises:
            Exception: Ошибка при создании события
        """
        try:
            # Формируем название события
            summary = f"Запись: {master_name} - {service_name}"
            
            # Создаем объект события для Google Calendar API
            event = {
                'summary': summary,
                'start': {
                    'dateTime': start_time_iso,
                    'timeZone': 'Europe/Moscow'
                },
                'end': {
                    'dateTime': end_time_iso,
                    'timeZone': 'Europe/Moscow'
                }
            }
            
            # Вызываем API для создания события
            created_event = self.service.events().insert(
                calendarId=self.calendar_id,
                body=event
            ).execute()
            
            return True
            
        except HttpError as error:
            raise Exception(f"Ошибка при создании записи: {error}")
    
    def create_event_legacy(
        self,
        summary: str,
        start_datetime: datetime,
        end_datetime: datetime,
        description: Optional[str] = None,
        location: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Создание нового события в календаре (legacy метод).
        
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
    
    def get_free_slots(self, date: str, duration_minutes: int) -> List[Dict[str, str]]:
        """
        Получает свободные временные интервалы на указанную дату.
        Ищет непрерывные интервалы, достаточные для выполнения услуги заданной длительности.
        
        Args:
            date: Дата в формате "YYYY-MM-DD"
            duration_minutes: Длительность услуги в минутах
        
        Returns:
            List[Dict[str, str]]: Список свободных интервалов в формате [{'start': '10:15', 'end': '13:45'}, ...]
        
        Raises:
            Exception: Ошибка при работе с API или неверный формат даты
        """
        try:
            # Парсим дату
            target_date = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            raise Exception(f"Неверный формат даты: {date}. Ожидается формат YYYY-MM-DD")
        
        # Определяем рабочее время салона (10:00 - 20:00)
        WORK_START_HOUR = 10
        WORK_END_HOUR = 20
        
        # Формируем временные рамки для поиска
        moscow_tz = ZoneInfo('Europe/Moscow')
        day_start = target_date.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=moscow_tz)
        day_end = target_date.replace(hour=23, minute=59, second=59, microsecond=999999, tzinfo=moscow_tz)
        
        # Получаем все события за этот день (для всех мастеров)
        events = self.get_events(time_min=day_start, time_max=day_end)
        
        # Создаем единый список всех занятых блоков
        occupied_blocks = []
        
        for event in events:
            start_str = event.get('start', {}).get('dateTime')
            end_str = event.get('end', {}).get('dateTime')
            
            if start_str and end_str:
                # Парсим время без timezone
                start_time = datetime.fromisoformat(start_str[:19])
                end_time = datetime.fromisoformat(end_str[:19])
                
                # Добавляем московский timezone
                start_time = start_time.replace(tzinfo=moscow_tz)
                end_time = end_time.replace(tzinfo=moscow_tz)
                
                occupied_blocks.append({
                    'start': start_time,
                    'end': end_time
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
        
        # Находим свободные интервалы
        free_intervals = []
        current_time = work_start
        
        for block in occupied_blocks:
            # Если текущее время до начала занятого блока
            if current_time < block['start']:
                # Проверяем, достаточно ли времени для услуги
                available_duration = (block['start'] - current_time).total_seconds() / 60
                if available_duration >= duration_minutes:
                    free_intervals.append({
                        'start': current_time.strftime('%H:%M'),
                        'end': block['start'].strftime('%H:%M')
                    })
            
            # Переходим к концу занятого блока
            current_time = max(current_time, block['end'])
        
        # Проверяем интервал после последнего занятого блока
        if current_time < work_end:
            available_duration = (work_end - current_time).total_seconds() / 60
            if available_duration >= duration_minutes:
                free_intervals.append({
                    'start': current_time.strftime('%H:%M'),
                    'end': work_end.strftime('%H:%M')
                })
        
        return free_intervals

