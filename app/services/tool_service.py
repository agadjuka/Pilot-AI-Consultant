from app.repositories.service_repository import ServiceRepository
from app.repositories.master_repository import MasterRepository
from app.services.google_calendar_service import GoogleCalendarService
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from difflib import SequenceMatcher


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
        # Сначала находим услугу по имени с нечетким поиском
        all_services = self.service_repository.get_all()
        service = self._find_service_by_fuzzy_match(service_name, all_services)

        if not service:
            # Если не найдено, показываем похожие услуги
            similar_services = self._find_similar_services(service_name, all_services)
            if similar_services:
                return f"Услуга с названием '{service_name}' не найдена. Возможно, вы имели в виду: {', '.join(similar_services)}?"
            return f"Услуга с названием '{service_name}' не найдена."

        # Теперь ищем мастеров для этой услуги
        masters = self.master_repository.get_masters_for_service(service.id)

        if not masters:
            return f"К сожалению, на данный момент нет мастеров, выполняющих услугу '{service.name}'."

        master_names = [master.name for master in masters]
        return f"Эту услугу выполняют мастера: {', '.join(master_names)}."

    def get_available_slots(self, service_name: str, date: str) -> str:
        """
        Получает свободные временные интервалы для услуги на указанную дату.
        Возвращает сырые данные для анализа LLM.

        Args:
            service_name: Название услуги
            date: Дата в формате строки (например, "2025-10-15")

        Returns:
            Компактная строка с интервалами свободного времени или сообщение об ошибке
        """
        try:
            # Находим услугу по имени с нечетким поиском
            all_services = self.service_repository.get_all()
            service = self._find_service_by_fuzzy_match(service_name, all_services)
            
            if not service:
                # Если не найдено, показываем похожие услуги
                similar_services = self._find_similar_services(service_name, all_services)
                if similar_services:
                    return f"Услуга '{service_name}' не найдена в нашем прайс-листе. Возможно, вы имели в виду: {', '.join(similar_services)}?"
                return f"Услуга '{service_name}' не найдена в нашем прайс-листе."
            
            # Получаем длительность услуги
            duration_minutes = service.duration_minutes

            # Получаем мастеров, выполняющих услугу
            masters = self.master_repository.get_masters_for_service(service.id)
            master_names = [m.name for m in masters] if masters else []
            
            # Получаем свободные интервалы из Google Calendar (учитывая занятость только этих мастеров)
            free_intervals = self.google_calendar_service.get_free_slots(
                date,
                duration_minutes,
                master_names=master_names
            )
            
            if not free_intervals:
                return f"На {date} нет свободных окон для услуги '{service_name}' (длительность {duration_minutes} мин)."
            
            # Преобразуем интервалы в компактную строку
            interval_strings = [f"{interval['start']}-{interval['end']}" for interval in free_intervals]
            return ", ".join(interval_strings)
            
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
            # Находим услугу в БД для получения длительности с нечетким поиском
            all_services = self.service_repository.get_all()
            service = self._find_service_by_fuzzy_match(service_name, all_services)
            
            if not service:
                # Если не найдено, показываем похожие услуги
                similar_services = self._find_similar_services(service_name, all_services)
                if similar_services:
                    return f"Услуга '{service_name}' не найдена в нашем прайс-листе. Возможно, вы имели в виду: {', '.join(similar_services)}?"
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

    def _find_service_by_fuzzy_match(self, service_name: str, all_services: list) -> object:
        """
        Находит услугу по нечеткому совпадению названия.
        
        Args:
            service_name: Название услуги для поиска
            all_services: Список всех услуг
            
        Returns:
            Найденная услуга или None
        """
        service_name_lower = service_name.lower().strip()
        
        # Сначала пробуем точное совпадение
        for service in all_services:
            if service.name.lower() == service_name_lower:
                return service
        
        # Затем пробуем нечеткое совпадение
        best_match = None
        best_ratio = 0.0
        
        for service in all_services:
            # Проверяем совпадение по словам
            service_words = service.name.lower().split()
            search_words = service_name_lower.split()
            
            # Если хотя бы одно слово совпадает точно
            for search_word in search_words:
                for service_word in service_words:
                    if search_word in service_word or service_word in search_word:
                        return service
            
            # Проверяем общее сходство строк
            ratio = SequenceMatcher(None, service_name_lower, service.name.lower()).ratio()
            if ratio > best_ratio and ratio > 0.6:  # Порог схожести 60%
                best_ratio = ratio
                best_match = service
        
        return best_match

    def _find_similar_services(self, service_name: str, all_services: list) -> list:
        """
        Находит похожие услуги для предложения альтернатив.
        
        Args:
            service_name: Название услуги для поиска
            all_services: Список всех услуг
            
        Returns:
            Список названий похожих услуг
        """
        service_name_lower = service_name.lower().strip()
        similar_services = []
        
        # Ищем услуги, содержащие ключевые слова
        keywords = service_name_lower.split()
        
        for service in all_services:
            service_lower = service.name.lower()
            
            # Если хотя бы одно ключевое слово есть в названии услуги
            for keyword in keywords:
                if keyword in service_lower and len(keyword) > 2:  # Игнорируем короткие слова
                    similar_services.append(service.name)
                    break
        
        # Убираем дубликаты и ограничиваем количество
        return list(set(similar_services))[:3]

