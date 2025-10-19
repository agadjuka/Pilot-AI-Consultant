from app.repositories.service_repository import ServiceRepository
from app.repositories.master_repository import MasterRepository
from app.services.appointment_service import AppointmentService
from app.services.db_calendar_service import DBCalendarService
from app.utils.robust_date_parser import parse_date_robust
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
        db_calendar_service: DBCalendarService,
        client_repository
    ):
        """
        Инициализирует ToolService с необходимыми репозиториями и сервисами.

        Args:
            service_repository: Репозиторий для работы с услугами
            master_repository: Репозиторий для работы с мастерами
            appointment_service: Сервис для управления записями
            db_calendar_service: Сервис для работы с календарем через БД
            client_repository: Репозиторий для работы с клиентами
        """
        self.service_repository = service_repository
        self.master_repository = master_repository
        self.appointment_service = appointment_service
        self.db_calendar_service = db_calendar_service
        self.client_repository = client_repository

    def _decode_string_field(self, field_value):
        """
        Декодирует байтовую строку в обычную строку, если необходимо.
        
        Args:
            field_value: Значение поля из базы данных
            
        Returns:
            Декодированная строка или исходное значение
        """
        if isinstance(field_value, bytes):
            return field_value.decode('utf-8')
        return field_value

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
            # Декодируем строковые поля из базы данных
            service_name = self._decode_string_field(service['name'])
            service_description = self._decode_string_field(service['description']) if service['description'] else None
            
            line = (
                f"Услуга: {service_name}, "
                f"Цена: {service['price']} руб., "
                f"Длительность: {service['duration_minutes']} мин."
            )
            if service_description:
                line += f" ({service_description})"
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
        masters = self.master_repository.get_masters_for_service(service['id'])

        if not masters:
            decoded_service_name = self._decode_string_field(service['name'])
            return f"К сожалению, на данный момент нет мастеров, выполняющих услугу '{decoded_service_name}'."

        master_names = [self._decode_string_field(master['name']) for master in masters]
        return f"Эту услугу выполняют мастера: {', '.join(master_names)}."

    def get_available_slots(self, service_name: str, date: str) -> str:
        """
        Получает свободные временные интервалы для услуги на указанную дату.
        Если на запрошенную дату мест нет, ищет ближайшие доступные слоты в течение 7 дней.
        Возвращает сырые данные для анализа LLM.

        Args:
            service_name: Название услуги
            date: Дата в любом поддерживаемом формате (например, "2025-10-15", "15.10.2025")

        Returns:
            Компактная строка с интервалами свободного времени или сообщение об ошибке
        """
        try:
            # Парсим дату в стандартный формат
            parsed_date = parse_date_robust(date)
            if parsed_date is None:
                return f"Неверный формат даты: {date}. Ожидается формат YYYY-MM-DD."
            
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
            duration_minutes = service['duration_minutes']

            # Получаем мастеров, выполняющих услугу
            masters = self.master_repository.get_masters_for_service(service['id'])
            master_names = [self._decode_string_field(m['name']) for m in masters] if masters else []
            
            # Получаем свободные интервалы из DBCalendarService для запрошенной даты
            free_intervals = self.db_calendar_service.get_free_slots(
                parsed_date,
                duration_minutes,
                master_names=master_names
            )
            
            # Если на запрошенную дату есть свободные слоты, возвращаем их
            if free_intervals:
                interval_strings = [f"{interval['start']}-{interval['end']}" for interval in free_intervals]
                return ", ".join(interval_strings)
            
            # Если на запрошенную дату мест нет, ищем ближайшие доступные слоты
            original_date = datetime.strptime(parsed_date, "%Y-%m-%d")
            
            for i in range(1, 8):  # Проверяем следующие 7 дней
                next_date = original_date + timedelta(days=i)
                next_date_str = next_date.strftime("%Y-%m-%d")
                
                # Получаем свободные интервалы для следующей даты
                next_free_intervals = self.db_calendar_service.get_free_slots(
                    next_date_str,
                    duration_minutes,
                    master_names=master_names
                )
                
                # Если нашли свободные слоты, возвращаем информацию о ближайшем окне
                if next_free_intervals:
                    first_interval = next_free_intervals[0]
                    return f"На {parsed_date} мест нет. Ближайшее окно: {next_date_str}, {first_interval['start']}-{first_interval['end']}"
            
            # Если за 7 дней ничего не найдено
            return f"На {parsed_date} и ближайшие 7 дней нет свободных окон для услуги '{service_name}' (длительность {duration_minutes} мин)."
            
        except Exception as e:
            return f"Ошибка при поиске свободных слотов: {str(e)}"

    def create_appointment(self, master_name: str, service_name: str, date: str, time: str, client_name: str, user_telegram_id: int) -> str:
        """
        Создает запись в календаре для мастера и услуги.
        
        Args:
            master_name: Имя мастера
            service_name: Название услуги
            date: Дата в любом поддерживаемом формате (например, "2025-10-15", "15.10.2025")
            time: Время в формате "HH:MM"
            client_name: Имя клиента
            user_telegram_id: ID пользователя в Telegram
        
        Returns:
            Строка с подтверждением записи или сообщение об ошибке
        """
        # Парсим дату в стандартный формат
        parsed_date = parse_date_robust(date)
        if parsed_date is None:
            return f"Неверный формат даты: {date}. Ожидается формат YYYY-MM-DD."
        
        return self.appointment_service.create_appointment(
            master_name=master_name,
            service_name=service_name,
            date=parsed_date,
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




    def get_my_appointments(self, user_telegram_id: int) -> str:
        """
        Получает все предстоящие записи пользователя в текстовом виде.
        
        Args:
            user_telegram_id: ID пользователя в Telegram
        
        Returns:
            Текстовое сообщение с записями или сообщение об их отсутствии
        """
        appointments = self.appointment_service.get_my_appointments(user_telegram_id=user_telegram_id)
        if not appointments:
            return "У вас нет предстоящих записей."
        
        result = "Ваши предстоящие записи:\n"
        for appointment in appointments:
            result += f"- {appointment['details']}\n"
        return result

    def cancel_appointment_by_id(self, appointment_id: int, user_telegram_id: int) -> str:
        """
        Отменяет запись по её ID.
        
        Args:
            appointment_id: ID записи для отмены
            user_telegram_id: ID пользователя в Telegram
        
        Returns:
            Подтверждение отмены или сообщение об ошибке
        """
        return self.appointment_service.cancel_appointment_by_id(appointment_id=appointment_id, user_telegram_id=user_telegram_id)

    def reschedule_appointment_by_id(self, appointment_id: int, new_date: str, new_time: str, user_telegram_id: int) -> str:
        """
        Переносит запись на новую дату и время по её ID.
        
        Args:
            appointment_id: ID записи для переноса
            new_date: Новая дата в любом поддерживаемом формате (например, "2025-10-15", "15.10.2025")
            new_time: Новое время в формате "HH:MM"
            user_telegram_id: ID пользователя в Telegram
        
        Returns:
            Подтверждение переноса или сообщение об ошибке
        """
        # Парсим дату в стандартный формат
        parsed_date = parse_date_robust(new_date)
        if parsed_date is None:
            return f"Неверный формат даты: {new_date}. Ожидается формат YYYY-MM-DD."
        
        return self.appointment_service.reschedule_appointment_by_id(
            appointment_id=appointment_id,
            new_date=parsed_date,
            new_time=new_time,
            user_telegram_id=user_telegram_id
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
        logger.info(f"🔧 [TOOL EXECUTION] Начало выполнения инструмента: tool_name='{tool_name}', parameters={parameters}, user_id={user_id}")
        
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
                logger.info(f"📝 [TOOL EXECUTION] Выполнение создания записи: master='{master_name}', service='{service_name}', date='{date}', time='{time}', client='{client_name}'")
                result = self.create_appointment(master_name, service_name, date, time, client_name, user_id)
                logger.info(f"✅ [TOOL EXECUTION] Результат создания записи: {result}")
                return result
            
            elif tool_name == "call_manager":
                reason = parameters.get("reason", "")
                result = self.call_manager(reason)
                return result.get("response_to_user", "Менеджер уведомлен")
            
            elif tool_name == "get_my_appointments":
                logger.info(f"📋 [TOOL EXECUTION] Выполнение получения записей пользователя: user_id={user_id}")
                appointments = self.get_my_appointments(user_id)
                if not appointments:
                    logger.info(f"📭 [TOOL EXECUTION] У пользователя нет предстоящих записей: user_id={user_id}")
                    return "У вас нет предстоящих записей."
                result = "Ваши предстоящие записи:\n"
                for appointment in appointments:
                    result += f"- {appointment['details']}\n"
                logger.info(f"✅ [TOOL EXECUTION] Найдено записей: {len(appointments)} для user_id={user_id}")
                return result
            
            elif tool_name == "cancel_appointment_by_id":
                # Поддерживаем как полное имя параметра, так и сокращенное
                appointment_id = parameters.get("appointment_id") or parameters.get("id")
                if appointment_id is None:
                    logger.warning(f"❌ [TOOL EXECUTION] Отсутствует appointment_id для отмены записи. Полученные параметры: {parameters}")
                    return "Ошибка: не указан ID записи для отмены"
                
                # Преобразуем в int, если передано как строка
                try:
                    appointment_id = int(appointment_id)
                except (ValueError, TypeError):
                    logger.warning(f"❌ [TOOL EXECUTION] Неверный формат appointment_id: {appointment_id}")
                    return "Ошибка: неверный формат ID записи"
                
                logger.info(f"🗑️ [TOOL EXECUTION] Выполнение отмены записи: appointment_id={appointment_id}")
                result = self.cancel_appointment_by_id(appointment_id, user_id)
                logger.info(f"✅ [TOOL EXECUTION] Результат отмены записи: {result}")
                return result
            
            elif tool_name == "reschedule_appointment_by_id":
                # Поддерживаем как полное имя параметра, так и сокращенное
                appointment_id = parameters.get("appointment_id") or parameters.get("id")
                new_date = parameters.get("new_date", "")
                new_time = parameters.get("new_time", "")
                if appointment_id is None:
                    logger.warning(f"❌ [TOOL EXECUTION] Отсутствует appointment_id для переноса записи. Полученные параметры: {parameters}")
                    return "Ошибка: не указан ID записи для переноса"
                
                # Преобразуем в int, если передано как строка
                try:
                    appointment_id = int(appointment_id)
                except (ValueError, TypeError):
                    logger.warning(f"❌ [TOOL EXECUTION] Неверный формат appointment_id: {appointment_id}")
                    return "Ошибка: неверный формат ID записи"
                
                logger.info(f"📅 [TOOL EXECUTION] Выполнение переноса записи: appointment_id={appointment_id}, new_date='{new_date}', new_time='{new_time}'")
                result = self.reschedule_appointment_by_id(appointment_id, new_date, new_time, user_id)
                logger.info(f"✅ [TOOL EXECUTION] Результат переноса записи: {result}")
                return result
            
            elif tool_name == "get_full_history":
                return self.get_full_history()
            
            elif tool_name == "save_client_name":
                name = parameters.get("name", "")
                logger.info(f"👤 [TOOL EXECUTION] Сохранение имени клиента: name='{name}', user_id={user_id}")
                result = self.save_client_name(name, user_id)
                logger.info(f"✅ [TOOL EXECUTION] Результат сохранения имени: {result}")
                return result
            
            elif tool_name == "save_client_phone":
                phone = parameters.get("phone", "")
                logger.info(f"📞 [TOOL EXECUTION] Сохранение телефона клиента: phone='{phone}', user_id={user_id}")
                result = self.save_client_phone(phone, user_id)
                logger.info(f"✅ [TOOL EXECUTION] Результат сохранения телефона: {result}")
                return result
            
            else:
                raise ValueError(f"Неизвестный инструмент: {tool_name}")
                
        except Exception as e:
            logger.error(f"❌ [TOOL EXECUTION] Критическая ошибка выполнения инструмента {tool_name}: {e}")
            return f"Ошибка выполнения {tool_name}: {str(e)}"

    def get_full_history(self) -> str:
        """
        Получает полную историю диалога для анализа контекста.
        
        Returns:
            Строка с информацией о запросе истории диалога
        """
        return "Запрошена полная история. (в будущем здесь будет логика)"

    def save_client_name(self, name: str, user_telegram_id: int) -> str:
        """
        Сохраняет имя клиента в базу данных.
        
        Args:
            name: Имя клиента для сохранения
            user_telegram_id: ID пользователя в Telegram
            
        Returns:
            Подтверждение сохранения или сообщение об ошибке
        """
        try:
            # Получаем или создаем клиента
            client = self.client_repository.get_or_create_by_telegram_id(user_telegram_id)
            
            # Если имя уже есть, не перезаписываем
            if client['first_name']:
                decoded_first_name = self._decode_string_field(client['first_name'])
                logger.info(f"ℹ️ Имя клиента {user_telegram_id} уже сохранено: '{decoded_first_name}'")
                return f"Имя уже сохранено: {decoded_first_name}"
            
            # Обновляем имя
            self.client_repository.update(client['id'], {'first_name': name})
            logger.info(f"✅ Имя клиента {user_telegram_id} сохранено: '{name}'")
            return f"Имя '{name}' сохранено"
            
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения имени клиента {user_telegram_id}: {e}")
            return f"Ошибка сохранения имени: {str(e)}"

    def save_client_phone(self, phone: str, user_telegram_id: int) -> str:
        """
        Сохраняет номер телефона клиента в базу данных.
        
        Args:
            phone: Номер телефона для сохранения
            user_telegram_id: ID пользователя в Telegram
            
        Returns:
            Подтверждение сохранения или сообщение об ошибке
        """
        try:
            # Нормализуем номер телефона
            normalized_phone = self._normalize_phone(phone)
            
            # Получаем или создаем клиента
            client = self.client_repository.get_or_create_by_telegram_id(user_telegram_id)
            
            # Если телефон уже есть, не перезаписываем
            if client['phone_number']:
                decoded_phone = self._decode_string_field(client['phone_number'])
                logger.info(f"ℹ️ Телефон клиента {user_telegram_id} уже сохранен: '{decoded_phone}'")
                return f"Телефон уже сохранен: {decoded_phone}"
            
            # Обновляем телефон
            self.client_repository.update(client['id'], {'phone_number': normalized_phone})
            logger.info(f"✅ Телефон клиента {user_telegram_id} сохранен: '{normalized_phone}'")
            return f"Телефон '{normalized_phone}' сохранен"
            
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения телефона клиента {user_telegram_id}: {e}")
            return f"Ошибка сохранения телефона: {str(e)}"

    def _normalize_phone(self, phone: str) -> str:
        """
        Нормализует номер телефона к стандартному формату +7XXXXXXXXXX.
        
        Args:
            phone: Номер телефона в любом формате
            
        Returns:
            Нормализованный номер телефона
        """
        import re
        
        # Убираем все пробелы, дефисы и скобки
        cleaned = re.sub(r'[\s\-\(\)]', '', phone)
        
        # Если номер начинается с 8, заменяем на +7
        if cleaned.startswith('8'):
            cleaned = '+7' + cleaned[1:]
        
        # Если номер начинается с 7, добавляем +
        elif cleaned.startswith('7'):
            cleaned = '+' + cleaned
        
        # Если номер не начинается с +, добавляем +7
        elif not cleaned.startswith('+'):
            cleaned = '+7' + cleaned
        
        return cleaned

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
            decoded_service_name = self._decode_string_field(service['name'])
            if decoded_service_name.lower() == service_name_lower:
                return service
        
        # Затем пробуем нечеткое совпадение
        best_match = None
        best_ratio = 0.0
        
        for service in all_services:
            decoded_service_name = self._decode_string_field(service['name'])
            # Проверяем совпадение по словам
            service_words = decoded_service_name.lower().split()
            search_words = service_name_lower.split()
            
            # Если хотя бы одно слово совпадает точно
            for search_word in search_words:
                for service_word in service_words:
                    if search_word in service_word or service_word in search_word:
                        return service
            
            # Проверяем общее сходство строк
            ratio = SequenceMatcher(None, service_name_lower, decoded_service_name.lower()).ratio()
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
            decoded_service_name = self._decode_string_field(service['name'])
            service_lower = decoded_service_name.lower()
            
            # Если хотя бы одно ключевое слово есть в названии услуги
            for keyword in keywords:
                if keyword in service_lower and len(keyword) > 2:  # Игнорируем короткие слова
                    similar_services.append(decoded_service_name)
                    break
        
        # Убираем дубликаты и ограничиваем количество
        return list(set(similar_services))[:3]

