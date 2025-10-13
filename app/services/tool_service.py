from app.repositories.service_repository import ServiceRepository
from app.repositories.master_repository import MasterRepository
from app.services.google_calendar_service import GoogleCalendarService
from app.services.slot_formatter import SlotFormatter
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


class ToolService:
    """
    Сервис-инструментарий для Function Calling.
    Содержит функции-инструменты для получения информации из базы данных.
    """

    def __init__(
        self,
        service_repository: ServiceRepository,
        master_repository: MasterRepository,
        google_calendar_service: GoogleCalendarService
    ):
        """
        Инициализирует ToolService с необходимыми репозиториями и сервисами.

        Args:
            service_repository: Репозиторий для работы с услугами
            master_repository: Репозиторий для работы с мастерами
            google_calendar_service: Сервис для работы с Google Calendar
        """
        self.service_repository = service_repository
        self.master_repository = master_repository
        self.google_calendar_service = google_calendar_service

    def get_all_services(self) -> str:
        """
        Получает список всех услуг из базы данных.

        Returns:
            Отформатированная строка со списком всех услуг
        """
        services = self.service_repository.get_all()

        if not services:
            return "На данный момент услуги недоступны."

        result_lines = []
        for service in services:
            line = (
                f"Услуга: {service.name}, "
                f"Цена: {service.price} руб., "
                f"Длительность: {service.duration_minutes} мин."
            )
            if service.description:
                line += f" ({service.description})"
            result_lines.append(line)

        return "\n".join(result_lines)

    def get_masters_for_service(self, service_name: str) -> str:
        """
        Находит мастеров, которые выполняют указанную услугу.

        Args:
            service_name: Название услуги для поиска

        Returns:
            Отформатированная строка с именами мастеров или сообщение об ошибке
        """
        # Сначала находим услугу по имени
        all_services = self.service_repository.get_all()
        service = None

        for s in all_services:
            if s.name.lower() == service_name.lower():
                service = s
                break

        if not service:
            return f"Услуга с названием '{service_name}' не найдена."

        # Теперь ищем мастеров для этой услуги
        masters = self.master_repository.get_masters_for_service(service.id)

        if not masters:
            return f"К сожалению, на данный момент нет мастеров, выполняющих услугу '{service_name}'."

        master_names = [master.name for master in masters]
        return f"Эту услугу выполняют мастера: {', '.join(master_names)}."

    def get_available_slots(self, service_name: str, master_name: str, date: str) -> str:
        """
        Получает свободные временные слоты для услуги у мастера на указанную дату.
        Группирует слоты в человекочитаемые диапазоны времени.

        Args:
            service_name: Название услуги
            master_name: Имя мастера (должен быть определен из контекста диалога)
            date: Дата в формате строки (например, "2025-10-15")

        Returns:
            Отформатированная строка с диапазонами свободного времени
        """
        try:
            # Находим услугу по имени
            all_services = self.service_repository.get_all()
            service = None
            
            for s in all_services:
                if s.name.lower() == service_name.lower():
                    service = s
                    break
            
            if not service:
                return f"Услуга '{service_name}' не найдена в нашем прайс-листе."
            
            # Получаем длительность услуги
            duration_minutes = service.duration_minutes
            
            # Получаем свободные слоты из Google Calendar с учетом длительности
            free_slots = self.google_calendar_service.get_free_slots(
                master_name, 
                date, 
                duration_minutes
            )
            
            # Форматируем ответ для пользователя
            if not free_slots:
                return f"К сожалению, на {date} у мастера {master_name} нет свободных окон для услуги '{service_name}' (длительность {duration_minutes} мин)."
            
            # Форматируем слоты в диапазоны
            formatted_ranges = SlotFormatter.format_slots_to_ranges(free_slots)
            
            return f"На {date} у мастера {master_name} есть свободные окна для услуги '{service_name}': {formatted_ranges}."
            
        except Exception as e:
            return f"Ошибка при поиске свободных слотов: {str(e)}"

    def create_appointment(self, master_name: str, service_name: str, date: str, time: str) -> str:
        """
        Создает запись в календаре для мастера и услуги.
        
        Args:
            master_name: Имя мастера
            service_name: Название услуги
            date: Дата в формате "YYYY-MM-DD"
            time: Время в формате "HH:MM"
        
        Returns:
            Строка с подтверждением записи или сообщение об ошибке
        """
        try:
            # Находим услугу в БД для получения длительности
            all_services = self.service_repository.get_all()
            service = None
            
            for s in all_services:
                if s.name.lower() == service_name.lower():
                    service = s
                    break
            
            if not service:
                return f"Услуга '{service_name}' не найдена в нашем прайс-листе."
            
            # Получаем длительность услуги
            duration_minutes = service.duration_minutes
            
            # Преобразуем date и time в объекты datetime
            try:
                # Парсим дату и время
                appointment_date = datetime.strptime(date, "%Y-%m-%d")
                appointment_time = datetime.strptime(time, "%H:%M")
                
                # Объединяем дату и время
                start_datetime = appointment_date.replace(
                    hour=appointment_time.hour,
                    minute=appointment_time.minute,
                    second=0,
                    microsecond=0
                )
                
                # Вычисляем время окончания
                end_datetime = start_datetime + timedelta(minutes=duration_minutes)
                
            except ValueError as e:
                return f"Ошибка в формате даты или времени: {str(e)}"
            
            # Конвертируем время в формат ISO 8601
            moscow_tz = ZoneInfo('Europe/Moscow')
            start_datetime = start_datetime.replace(tzinfo=moscow_tz)
            end_datetime = end_datetime.replace(tzinfo=moscow_tz)
            
            start_time_iso = start_datetime.strftime('%Y-%m-%dT%H:%M:%S')
            end_time_iso = end_datetime.strftime('%Y-%m-%dT%H:%M:%S')
            
            # Вызываем метод создания события в Google Calendar
            success = self.google_calendar_service.create_event(
                master_name=master_name,
                service_name=service_name,
                start_time_iso=start_time_iso,
                end_time_iso=end_time_iso
            )
            
            if success:
                return f"Отлично! Я записала вас на {service_name} к мастеру {master_name} на {date} в {time}."
            else:
                return f"Произошла ошибка при создании записи. Попробуйте еще раз."
                
        except Exception as e:
            return f"Ошибка при создании записи: {str(e)}"

