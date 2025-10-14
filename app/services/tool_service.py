from app.repositories.service_repository import ServiceRepository
from app.repositories.master_repository import MasterRepository
from app.services.appointment_service import AppointmentService
from datetime import datetime, timedelta
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
        appointment_service: AppointmentService
    ):
        """
        Инициализирует ToolService с необходимыми репозиториями и сервисами.

        Args:
            service_repository: Репозиторий для работы с услугами
            master_repository: Репозиторий для работы с мастерами
            appointment_service: Сервис для управления записями
        """
        self.service_repository = service_repository
        self.master_repository = master_repository
        self.appointment_service = appointment_service

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
        print(f"!!! MANAGER ALERT: {reason} !!!")
        
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

