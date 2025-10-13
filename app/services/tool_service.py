from app.repositories.service_repository import ServiceRepository
from app.repositories.master_repository import MasterRepository
from app.services.google_calendar_service import GoogleCalendarService
from app.services.slot_formatter import SlotFormatter


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

