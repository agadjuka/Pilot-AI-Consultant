from app.repositories.service_repository import ServiceRepository
from app.repositories.master_repository import MasterRepository


class ToolService:
    """
    Сервис-инструментарий для Function Calling.
    Содержит функции-инструменты для получения информации из базы данных.
    """

    def __init__(
        self,
        service_repository: ServiceRepository,
        master_repository: MasterRepository
    ):
        """
        Инициализирует ToolService с необходимыми репозиториями.

        Args:
            service_repository: Репозиторий для работы с услугами
            master_repository: Репозиторий для работы с мастерами
        """
        self.service_repository = service_repository
        self.master_repository = master_repository

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

    def get_available_slots(self, master_name: str, date: str) -> str:
        """
        Получает свободные временные слоты для мастера на указанную дату.
        
        ВНИМАНИЕ: Это заглушка. Реальная интеграция с календарем будет реализована позже.

        Args:
            master_name: Имя мастера
            date: Дата в формате строки (например, "2025-10-15")

        Returns:
            Отформатированная строка со списком свободных слотов
        """
        # Заглушка: возвращаем статичные слоты
        return f"Свободные слоты для мастера {master_name} на {date}: 10:00, 12:00, 15:00."

