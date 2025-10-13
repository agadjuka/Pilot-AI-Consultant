"""
Сервис для работы с Google Calendar API.
Используется единый календарь для всех мастеров.
"""
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
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
        event = {
            'summary': summary,
            'description': description,
            'location': location,
            'start': {
                'dateTime': start_datetime.isoformat(),
                'timeZone': 'Europe/Moscow',
            },
            'end': {
                'dateTime': end_datetime.isoformat(),
                'timeZone': 'Europe/Moscow',
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
                params['timeMin'] = time_min.isoformat() + 'Z'
            if time_max:
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

