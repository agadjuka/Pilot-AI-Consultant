from app.repositories.service_repository import ServiceRepository
from app.repositories.master_repository import MasterRepository
from app.services.appointment_service import AppointmentService
from app.services.google_calendar_service import GoogleCalendarService
from datetime import datetime, timedelta
from difflib import SequenceMatcher
import logging

# Получаем логгер для этого модуля
logger = logging.getLogger(__name__)


class ToolService:
    """
    Сервис-инструментарий для Function Calling.
    Содержит функции-инструменты для получения информации из базы данных.
    """

    def __init__(
        self,
        service_repository: ServiceRepository,
        master_repository: MasterRepository,
        appointment_service: AppointmentService,
        google_calendar_service: GoogleCalendarService
    ):
        """
        Инициализирует ToolService с необходимыми репозиториями и сервисами.

        Args:
            service_repository: Репозиторий для работы с услугами
            master_repository: Репозиторий для работы с мастерами
            appointment_service: Сервис для управления записями
            google_calendar_service: Сервис для работы с Google Calendar
        """
        self.service_repository = service_repository
        self.master_repository = master_repository
        self.appointment_service = appointment_service
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
        return self.appointment_service.create_appointment(
            master_name=master_name,
            service_name=service_name,
            date=date,
            time=time,
            client_name=client_name,
            user_telegram_id=user_telegram_id
        )


    def call_manager(self, reason: str) -> dict:
        """
        Вызывает менеджера для эскалации сложного диалога.
        
        Args:
            reason: Причина вызова менеджера
            
        Returns:
            Словарь с ответом для пользователя и системным сигналом
        """
        # В будущем здесь будет логика отправки уведомления менеджеру
        logger.warning(f"🚨 MANAGER ALERT: {reason}")
        
        return {
            "response_to_user": "Секундочку, уточню у менеджера ваш вопрос.",
            "system_signal": "[CALL_MANAGER]"
        }




    def get_my_appointments(self, user_telegram_id: int) -> list:
        """
        Получает все предстоящие записи пользователя в структурированном виде.
        
        Args:
            user_telegram_id: ID пользователя в Telegram
        
        Returns:
            Список словарей с записями, где каждый словарь содержит 'id' и 'details'
        """
        return self.appointment_service.get_my_appointments(user_telegram_id=user_telegram_id)

    def cancel_appointment_by_id(self, appointment_id: int) -> str:
        """
        Отменяет запись по её ID.
        
        Args:
            appointment_id: ID записи для отмены
        
        Returns:
            Подтверждение отмены или сообщение об ошибке
        """
        return self.appointment_service.cancel_appointment_by_id(appointment_id=appointment_id)

    def reschedule_appointment_by_id(self, appointment_id: int, new_date: str, new_time: str) -> str:
        """
        Переносит запись на новую дату и время по её ID.
        
        Args:
            appointment_id: ID записи для переноса
            new_date: Новая дата в формате "YYYY-MM-DD"
            new_time: Новое время в формате "HH:MM"
        
        Returns:
            Подтверждение переноса или сообщение об ошибке
        """
        return self.appointment_service.reschedule_appointment_by_id(
            appointment_id=appointment_id,
            new_date=new_date,
            new_time=new_time
        )

    async def execute_tool(self, tool_name: str, parameters: dict, user_id: int) -> str:
        """
        Выполняет указанный инструмент с заданными параметрами.
        
        Args:
            tool_name: Название инструмента для выполнения
            parameters: Параметры для инструмента
            user_id: ID пользователя Telegram
            
        Returns:
            Результат выполнения инструмента в виде строки
            
        Raises:
            ValueError: Если инструмент не найден
        """
        try:
            if tool_name == "get_all_services":
                return self.get_all_services()
            
            elif tool_name == "get_masters_for_service":
                service_name = parameters.get("service_name", "")
                return self.get_masters_for_service(service_name)
            
            elif tool_name == "get_available_slots":
                service_name = parameters.get("service_name", "")
                date = parameters.get("date", "")
                return self.get_available_slots(service_name, date)
            
            elif tool_name == "create_appointment":
                master_name = parameters.get("master_name", "")
                service_name = parameters.get("service_name", "")
                date = parameters.get("date", "")
                time = parameters.get("time", "")
                client_name = parameters.get("client_name", "")
                return self.create_appointment(master_name, service_name, date, time, client_name, user_id)
            
            elif tool_name == "call_manager":
                reason = parameters.get("reason", "")
                result = self.call_manager(reason)
                return result.get("response_to_user", "Менеджер уведомлен")
            
            elif tool_name == "get_my_appointments":
                appointments = self.get_my_appointments(user_id)
                if not appointments:
                    return "У вас нет предстоящих записей."
                result = "Ваши предстоящие записи:\n"
                for appointment in appointments:
                    result += f"- {appointment['details']}\n"
                return result
            
            elif tool_name == "cancel_appointment_by_id":
                appointment_id = parameters.get("appointment_id")
                if appointment_id is None:
                    return "Ошибка: не указан ID записи для отмены"
                return self.cancel_appointment_by_id(appointment_id)
            
            elif tool_name == "reschedule_appointment_by_id":
                appointment_id = parameters.get("appointment_id")
                new_date = parameters.get("new_date", "")
                new_time = parameters.get("new_time", "")
                if appointment_id is None:
                    return "Ошибка: не указан ID записи для переноса"
                return self.reschedule_appointment_by_id(appointment_id, new_date, new_time)
            
            elif tool_name == "get_full_history":
                return self.get_full_history()
            
            else:
                raise ValueError(f"Неизвестный инструмент: {tool_name}")
                
        except Exception as e:
            logger.error(f"Ошибка выполнения инструмента {tool_name}: {e}")
            return f"Ошибка выполнения {tool_name}: {str(e)}"

    def get_full_history(self) -> str:
        """
        Получает полную историю диалога для анализа контекста.
        
        Returns:
            Строка с информацией о запросе истории диалога
        """
        return "Запрошена полная история. (в будущем здесь будет логика)"

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

