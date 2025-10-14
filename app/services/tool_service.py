from app.repositories.service_repository import ServiceRepository
from app.repositories.master_repository import MasterRepository
from app.repositories.appointment_repository import AppointmentRepository
from app.services.google_calendar_service import GoogleCalendarService
from app.repositories.client_repository import ClientRepository
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
        appointment_repository: AppointmentRepository,
        google_calendar_service: GoogleCalendarService,
        client_repository: ClientRepository
    ):
        """
        Инициализирует ToolService с необходимыми репозиториями и сервисами.

        Args:
            service_repository: Репозиторий для работы с услугами
            master_repository: Репозиторий для работы с мастерами
            appointment_repository: Репозиторий для работы с записями
            google_calendar_service: Сервис для работы с Google Calendar
        """
        self.service_repository = service_repository
        self.master_repository = master_repository
        self.appointment_repository = appointment_repository
        self.google_calendar_service = google_calendar_service
        self.client_repository = client_repository

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
        Если на запрошенную дату мест нет, ищет ближайшие доступные слоты в течение 7 дней.
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
            
            # Получаем свободные интервалы из Google Calendar для запрошенной даты
            free_intervals = self.google_calendar_service.get_free_slots(
                date,
                duration_minutes,
                master_names=master_names
            )
            
            # Если на запрошенную дату есть свободные слоты, возвращаем их
            if free_intervals:
                interval_strings = [f"{interval['start']}-{interval['end']}" for interval in free_intervals]
                return ", ".join(interval_strings)
            
            # Если на запрошенную дату мест нет, ищем ближайшие доступные слоты
            original_date = datetime.strptime(date, "%Y-%m-%d")
            
            for i in range(1, 8):  # Проверяем следующие 7 дней
                next_date = original_date + timedelta(days=i)
                next_date_str = next_date.strftime("%Y-%m-%d")
                
                # Получаем свободные интервалы для следующей даты
                next_free_intervals = self.google_calendar_service.get_free_slots(
                    next_date_str,
                    duration_minutes,
                    master_names=master_names
                )
                
                # Если нашли свободные слоты, возвращаем информацию о ближайшем окне
                if next_free_intervals:
                    first_interval = next_free_intervals[0]
                    return f"На {date} мест нет. Ближайшее окно: {next_date_str}, {first_interval['start']}-{first_interval['end']}"
            
            # Если за 7 дней ничего не найдено
            return f"На {date} и ближайшие 7 дней нет свободных окон для услуги '{service_name}' (длительность {duration_minutes} мин)."
            
        except Exception as e:
            return f"Ошибка при поиске свободных слотов: {str(e)}"

    def create_appointment(self, master_name: str, service_name: str, date: str, time: str, client_name: str, user_telegram_id: int) -> str:
        """
        Создает запись в календаре для мастера и услуги.
        
        Args:
            master_name: Имя мастера
            service_name: Название услуги
            date: Дата в формате "YYYY-MM-DD"
            time: Время в формате "HH:MM"
            client_name: Имя клиента
            user_telegram_id: ID пользователя в Telegram
        
        Returns:
            Строка с подтверждением записи или сообщение об ошибке
        """
        try:
            # Проверка наличия контактных данных клиента
            client = self.client_repository.get_or_create_by_telegram_id(user_telegram_id)
            if not client.first_name or not client.phone_number:
                return "Требуются данные клиента. Перейди в стадию 'contact_info_request'."
            # Находим услугу в БД для получения длительности с нечетким поиском
            all_services = self.service_repository.get_all()
            service = self._find_service_by_fuzzy_match(service_name, all_services)
            
            if not service:
                # Если не найдено, показываем похожие услуги
                similar_services = self._find_similar_services(service_name, all_services)
                if similar_services:
                    return f"Услуга '{service_name}' не найдена в нашем прайс-листе. Возможно, вы имели в виду: {', '.join(similar_services)}?"
                return f"Услуга '{service_name}' не найдена в нашем прайс-листе."
            
            # Находим мастера в БД
            all_masters = self.master_repository.get_all()
            master = self._find_master_by_fuzzy_match(master_name, all_masters)
            
            if not master:
                # Если не найдено, показываем похожих мастеров
                similar_masters = self._find_similar_masters(master_name, all_masters)
                if similar_masters:
                    return f"Мастер '{master_name}' не найден. Возможно, вы имели в виду: {', '.join(similar_masters)}?"
                return f"Мастер '{master_name}' не найден."
            
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
            # Формируем описание события для мастера
            description = f"Клиент: {client.first_name or client_name} | Телефон: {client.phone_number or '-'} | Telegram ID: {user_telegram_id}"

            try:
                event_id = self.google_calendar_service.create_event(
                    master_name=master_name,
                    service_name=service_name,
                    start_time_iso=start_time_iso,
                    end_time_iso=end_time_iso,
                    description=description
                )
            except Exception as calendar_error:
                # Фолбэк: если интеграция с календарем недоступна (например, dev-среда),
                # создаем локальный event_id и продолжаем сохранение записи в БД
                # Это позволяет не блокировать продажи из-за внешнего сервиса
                from uuid import uuid4
                event_id = f"LOCAL-{uuid4()}"
                print(f"[WARN] Calendar unavailable, fallback to local event_id: {event_id}. Error: {calendar_error}")
            
            # Сохраняем запись в нашу БД
            appointment_data = {
                'user_telegram_id': user_telegram_id,
                'google_event_id': event_id,
                'master_id': master.id,
                'service_id': service.id,
                'start_time': start_datetime,
                'end_time': end_datetime
            }
            
            self.appointment_repository.create(appointment_data)
            
            return f"Отлично! Я записала {client.first_name or client_name} на {service_name} к мастеру {master_name} на {date} в {time}."
                
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

    def call_manager(self, reason: str) -> dict:
        """
        Вызывает менеджера для эскалации сложного диалога.
        
        Args:
            reason: Причина вызова менеджера
            
        Returns:
            Словарь с ответом для пользователя и системным сигналом
        """
        # В будущем здесь будет логика отправки уведомления менеджеру
        print(f"!!! MANAGER ALERT: {reason} !!!")
        
        return {
            "response_to_user": "Секундочку, уточню у менеджера ваш вопрос.",
            "system_signal": "[CALL_MANAGER]"
        }

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

    def _find_master_by_fuzzy_match(self, master_name: str, all_masters: list) -> object:
        """
        Находит мастера по нечеткому совпадению имени.
        
        Args:
            master_name: Имя мастера для поиска
            all_masters: Список всех мастеров
            
        Returns:
            Найденный мастер или None
        """
        master_name_lower = master_name.lower().strip()
        
        # Сначала пробуем точное совпадение
        for master in all_masters:
            if master.name.lower() == master_name_lower:
                return master
        
        # Затем пробуем нечеткое совпадение
        best_match = None
        best_ratio = 0.0
        
        for master in all_masters:
            # Проверяем совпадение по словам
            master_words = master.name.lower().split()
            search_words = master_name_lower.split()
            
            # Если хотя бы одно слово совпадает точно
            for search_word in search_words:
                for master_word in master_words:
                    if search_word in master_word or master_word in search_word:
                        return master
            
            # Проверяем общее сходство строк
            ratio = SequenceMatcher(None, master_name_lower, master.name.lower()).ratio()
            if ratio > best_ratio and ratio > 0.6:  # Порог схожести 60%
                best_ratio = ratio
                best_match = master
        
        return best_match

    def _find_similar_masters(self, master_name: str, all_masters: list) -> list:
        """
        Находит похожих мастеров для предложения альтернатив.
        
        Args:
            master_name: Имя мастера для поиска
            all_masters: Список всех мастеров
            
        Returns:
            Список имен похожих мастеров
        """
        master_name_lower = master_name.lower().strip()
        similar_masters = []
        
        # Ищем мастеров, содержащих ключевые слова
        keywords = master_name_lower.split()
        
        for master in all_masters:
            master_lower = master.name.lower()
            
            # Если хотя бы одно ключевое слово есть в имени мастера
            for keyword in keywords:
                if keyword in master_lower and len(keyword) > 2:  # Игнорируем короткие слова
                    similar_masters.append(master.name)
                    break
        
        # Убираем дубликаты и ограничиваем количество
        return list(set(similar_masters))[:3]

    def get_my_appointments(self, user_telegram_id: int) -> str:
        """
        Получает все предстоящие записи пользователя.
        
        Args:
            user_telegram_id: ID пользователя в Telegram
        
        Returns:
            Отформатированная строка с записями или сообщение об их отсутствии
        """
        try:
            appointments = self.appointment_repository.get_future_appointments_by_user(user_telegram_id)
            
            if not appointments:
                return "У вас нет предстоящих записей."
            
            result_lines = ["Ваши предстоящие записи:"]
            for appointment in appointments:
                # Форматируем дату и время
                date_str = appointment.start_time.strftime("%d %B")
                time_str = appointment.start_time.strftime("%H:%M")
                
                # Получаем информацию о мастере и услуге
                master_name = appointment.master.name
                service_name = appointment.service.name
                
                result_lines.append(f"- {date_str} в {time_str}: {service_name} к мастеру {master_name}.")
            
            return "\n".join(result_lines)
            
        except Exception as e:
            return f"Ошибка при получении записей: {str(e)}"

    def cancel_appointment(self, appointment_details: str, user_telegram_id: int) -> str:
        """
        Отменяет ближайшую предстоящую запись пользователя.
        
        Args:
            appointment_details: Описание записи для отмены (из слов клиента)
            user_telegram_id: ID пользователя в Telegram
        
        Returns:
            Подтверждение отмены или сообщение об ошибке
        """
        try:
            # Находим ближайшую предстоящую запись пользователя
            appointment = self.appointment_repository.get_next_appointment_by_user(user_telegram_id)
            
            if not appointment:
                return "У вас нет предстоящих записей для отмены."
            
            # Получаем информацию о записи
            master_name = appointment.master.name
            service_name = appointment.service.name
            date_str = appointment.start_time.strftime("%d %B")
            time_str = appointment.start_time.strftime("%H:%M")
            
            # Сначала пытаемся удалить событие в Google Calendar (не критично, если не удастся)
            try:
                self.google_calendar_service.delete_event(appointment.google_event_id)
            except Exception as calendar_error:
                # Логируем, но не блокируем удаление в БД
                print(f"[WARN] Не удалось удалить событие в календаре: {calendar_error}")

            # Удаляем запись из нашей БД напрямую по объекту и проверяем результат
            deleted = self.appointment_repository.delete(appointment)
            if not deleted:
                return "Не удалось отменить запись: запись не найдена или уже удалена."

            return f"Ваша запись на {service_name} {date_str} в {time_str} к мастеру {master_name} успешно отменена."
            
        except Exception as e:
            return f"Ошибка при отмене записи: {str(e)}"

