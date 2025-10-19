from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.client_repository import ClientRepository
from app.repositories.master_repository import MasterRepository
from app.repositories.service_repository import ServiceRepository
from app.services.db_calendar_service import DBCalendarService
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from difflib import SequenceMatcher
import logging

# Получаем логгер для этого модуля
logger = logging.getLogger(__name__)


class AppointmentService:
    """
    Сервис для управления записями (appointments).
    Отвечает за всю бизнес-логику создания, получения, отмены и переноса записей.
    """

    def __init__(
        self,
        appointment_repository: AppointmentRepository,
        client_repository: ClientRepository,
        master_repository: MasterRepository,
        service_repository: ServiceRepository,
        db_calendar_service: DBCalendarService
    ):
        """
        Инициализирует AppointmentService с необходимыми репозиториями и сервисами.

        Args:
            appointment_repository: Репозиторий для работы с записями
            client_repository: Репозиторий для работы с клиентами
            master_repository: Репозиторий для работы с мастерами
            service_repository: Репозиторий для работы с услугами
            db_calendar_service: Сервис для работы с календарем через БД
        """
        self.appointment_repository = appointment_repository
        self.client_repository = client_repository
        self.master_repository = master_repository
        self.service_repository = service_repository
        self.db_calendar_service = db_calendar_service

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
        logger.info(f"📝 [CREATE APPOINTMENT] Начало создания записи: user_id={user_telegram_id}, master='{master_name}', service='{service_name}', date='{date}', time='{time}', client='{client_name}'")
        
        try:
            # Проверка наличия контактных данных клиента
            client = self.client_repository.get_or_create_by_telegram_id(user_telegram_id)
            if not client['first_name'] or not client['phone_number']:
                decoded_first_name = self._decode_string_field(client['first_name']) if client['first_name'] else None
                decoded_phone = self._decode_string_field(client['phone_number']) if client['phone_number'] else None
                logger.warning(f"⚠️ [CREATE APPOINTMENT] Отсутствуют контактные данные клиента: user_id={user_telegram_id}, first_name='{decoded_first_name}', phone='{decoded_phone}'")
                return "Требуются данные клиента. Перейди в стадию 'contact_info_request'."
            
            decoded_first_name = self._decode_string_field(client['first_name'])
            decoded_phone = self._decode_string_field(client['phone_number'])
            logger.info(f"✅ [CREATE APPOINTMENT] Контактные данные клиента найдены: user_id={user_telegram_id}, name='{decoded_first_name}', phone='{decoded_phone}'")
            
            # Находим услугу в БД для получения длительности с простым поиском
            all_services = self.service_repository.get_all()
            service = next((s for s in all_services if service_name.lower() in s['name'].lower()), None)
            
            if not service:
                # Если не найдено, показываем похожие услуги
                similar_services = self._find_similar_services(service_name, all_services)
                logger.warning(f"❌ [CREATE APPOINTMENT] Услуга не найдена: '{service_name}', похожие: {similar_services}")
                if similar_services:
                    return f"Услуга '{service_name}' не найдена в нашем прайс-листе. Возможно, вы имели в виду: {', '.join(similar_services)}?"
                return f"Услуга '{service_name}' не найдена в нашем прайс-листе."
            
            decoded_service_name = self._decode_string_field(service['name'])
            logger.info(f"✅ [CREATE APPOINTMENT] Услуга найдена: id={service['id']}, name='{decoded_service_name}', duration={service['duration_minutes']} мин, price={service['price']} руб")
            
            # Находим мастера в БД
            all_masters = self.master_repository.get_all()
            
            # Если мастер не указан, автоматически выбираем первого доступного мастера для этой услуги
            if not master_name or master_name.strip() == "":
                decoded_service_name = self._decode_string_field(service['name'])
                logger.info(f"🔍 [CREATE APPOINTMENT] Мастер не указан, ищем доступного мастера для услуги '{decoded_service_name}'")
                available_masters = self.master_repository.get_masters_for_service(service['id'])
                if available_masters:
                    master = available_masters[0]  # Берем первого доступного мастера
                    decoded_master_name = self._decode_string_field(master['name'])
                    logger.info(f"✅ [CREATE APPOINTMENT] Автоматически выбран мастер: id={master['id']}, name='{decoded_master_name}'")
                else:
                    decoded_service_name = self._decode_string_field(service['name'])
                    logger.warning(f"❌ [CREATE APPOINTMENT] Нет доступных мастеров для услуги '{decoded_service_name}'")
                    return f"К сожалению, сейчас нет доступных мастеров для услуги '{decoded_service_name}'."
            else:
                master = next((m for m in all_masters if master_name.lower() in m['name'].lower()), None)
                
                if not master:
                    # Если не найдено, показываем похожих мастеров
                    similar_masters = self._find_similar_masters(master_name, all_masters)
                    logger.warning(f"❌ [CREATE APPOINTMENT] Мастер не найден: '{master_name}', похожие: {similar_masters}")
                    if similar_masters:
                        return f"Мастер '{master_name}' не найден. Возможно, вы имели в виду: {', '.join(similar_masters)}?"
                    return f"Мастер '{master_name}' не найден."
                
                decoded_master_name = self._decode_string_field(master['name'])
                logger.info(f"✅ [CREATE APPOINTMENT] Мастер найден: id={master['id']}, name='{decoded_master_name}'")
            
            # Получаем длительность услуги
            duration_minutes = service['duration_minutes']
            
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
                logger.error(f"❌ [CREATE APPOINTMENT] Ошибка парсинга даты/времени: {str(e)}")
                return f"Ошибка в формате даты или времени: {str(e)}"
            
            logger.info(f"📅 [CREATE APPOINTMENT] Время записи: {start_datetime} - {end_datetime} (длительность: {duration_minutes} мин)")
            
            # Конвертируем время в формат ISO 8601
            moscow_tz = ZoneInfo('Europe/Moscow')
            start_datetime = start_datetime.replace(tzinfo=moscow_tz)
            end_datetime = end_datetime.replace(tzinfo=moscow_tz)
            
            start_time_iso = start_datetime.strftime('%Y-%m-%dT%H:%M:%S')
            end_time_iso = end_datetime.strftime('%Y-%m-%dT%H:%M:%S')
            
            # Создаем запись через DBCalendarService
            # Формируем описание события для мастера
            decoded_first_name = self._decode_string_field(client['first_name']) if client['first_name'] else None
            decoded_phone = self._decode_string_field(client['phone_number']) if client['phone_number'] else None
            description = f"Клиент: {decoded_first_name or client_name} | Телефон: {decoded_phone or '-'} | Telegram ID: {user_telegram_id}"

            try:
                appointment_id = self.db_calendar_service.create_event(
                    master_id=master['id'],
                    service_id=service['id'],
                    user_telegram_id=user_telegram_id,
                    start_time=start_datetime,
                    end_time=end_datetime,
                    description=description
                )
                logger.info(f"✅ [CREATE APPOINTMENT] Запись создана через DBCalendarService: appointment_id={appointment_id}")
            except Exception as calendar_error:
                logger.error(f"❌ [CREATE APPOINTMENT] Ошибка создания записи через DBCalendarService: {calendar_error}")
                return f"Ошибка при создании записи: {str(calendar_error)}"
            
            decoded_first_name = self._decode_string_field(client['first_name']) if client['first_name'] else None
            success_message = f"Отлично! Я записала {decoded_first_name or client_name} на {service_name} к мастеру {master_name} на {date} в {time}."
            logger.info(f"🎉 [CREATE APPOINTMENT] Успешно завершено: {success_message}")
            return success_message
                
        except Exception as e:
            logger.error(f"❌ [CREATE APPOINTMENT] Критическая ошибка: {str(e)}")
            return f"Ошибка при создании записи: {str(e)}"

    def get_my_appointments(self, user_telegram_id: int) -> list:
        """
        Получает все предстоящие записи пользователя в структурированном виде.
        
        Args:
            user_telegram_id: ID пользователя в Telegram
        
        Returns:
            Список словарей с записями, где каждый словарь содержит 'id' и 'details'
        """
        logger.info(f"📋 [GET MY APPOINTMENTS] Получение записей пользователя: user_id={user_telegram_id}")
        
        try:
            appointments = self.appointment_repository.get_future_appointments_by_user(user_telegram_id)
            
            if not appointments:
                logger.info(f"📭 [GET MY APPOINTMENTS] У пользователя нет предстоящих записей: user_id={user_telegram_id}")
                return []
            
            logger.info(f"📋 [GET MY APPOINTMENTS] Найдено записей: {len(appointments)} для user_id={user_telegram_id}")
            
            result = []
            for appointment in appointments:
                # Получаем данные мастера и услуги
                master = self.master_repository.get_by_id(appointment['master_id'])
                service = self.service_repository.get_by_id(appointment['service_id'])
                
                if not master or not service:
                    logger.warning(f"⚠️ [GET MY APPOINTMENTS] Не найдены данные мастера или услуги для записи {appointment['id']}")
                    continue
                
                # Форматируем дату и время
                start_time = datetime.fromisoformat(appointment['start_time'].replace('Z', '+00:00'))
                date_str = start_time.strftime("%d %B")
                time_str = start_time.strftime("%H:%M")
                
                # Получаем информацию о мастере и услуге
                master_name = self._decode_string_field(master['name'])
                service_name = self._decode_string_field(service['name'])
                
                details = f"{date_str} в {time_str}: {service_name} к мастеру {master_name}"
                
                logger.info(f"📅 [GET MY APPOINTMENTS] Запись: id={appointment['id']}, {details}")
                
                result.append({
                    "id": appointment['id'],
                    "details": details
                })
            
            logger.info(f"✅ [GET MY APPOINTMENTS] Успешно получено {len(result)} записей для user_id={user_telegram_id}")
            return result
            
        except Exception as e:
            logger.error(f"❌ [GET MY APPOINTMENTS] Ошибка получения записей: user_id={user_telegram_id}, error={str(e)}")
            return []

    def cancel_appointment_by_id(self, appointment_id: int, user_telegram_id: int) -> str:
        """
        Отменяет запись по её ID.
        
        Args:
            appointment_id: ID записи для отмены
            user_telegram_id: ID пользователя в Telegram для проверки прав доступа
        
        Returns:
            Подтверждение отмены или сообщение об ошибке
        """
        logger.info(f"🗑️ [CANCEL APPOINTMENT] Начало отмены записи: appointment_id={appointment_id}, user_id={user_telegram_id}")
        
        try:
            # Проверяем права доступа
            appointment = self.appointment_repository.get_by_id(appointment_id)
            if not appointment or appointment['user_telegram_id'] != user_telegram_id:
                logger.warning(f"❌ [CANCEL APPOINTMENT] Нет прав доступа: appointment_id={appointment_id}, user_id={user_telegram_id}, appointment_user_id={appointment['user_telegram_id'] if appointment else 'None'}")
                return "Запись не найдена или у вас нет прав для её отмены."
            
            logger.info(f"✅ [CANCEL APPOINTMENT] Права доступа подтверждены: appointment_id={appointment_id}, user_id={user_telegram_id}")
            
            # Получаем информацию о записи
            master = self.master_repository.get_by_id(appointment['master_id'])
            service = self.service_repository.get_by_id(appointment['service_id'])
            
            if not master or not service:
                logger.warning(f"⚠️ [CANCEL APPOINTMENT] Не найдены данные мастера или услуги для записи {appointment_id}")
                return "Ошибка: не найдены данные о записи."
            
            master_name = self._decode_string_field(master['name'])
            service_name = self._decode_string_field(service['name'])
            start_time = datetime.fromisoformat(appointment['start_time'].replace('Z', '+00:00'))
            date_str = start_time.strftime("%d %B")
            time_str = start_time.strftime("%H:%M")
            
            logger.info(f"📋 [CANCEL APPOINTMENT] Информация о записи: master='{master_name}', service='{service_name}', date='{date_str}', time='{time_str}'")
            
            # Удаляем запись через DBCalendarService
            try:
                self.db_calendar_service.delete_event(appointment_id)
                logger.info(f"✅ [CANCEL APPOINTMENT] Запись удалена через DBCalendarService: appointment_id={appointment_id}")
            except Exception as calendar_error:
                logger.error(f"❌ [CANCEL APPOINTMENT] Ошибка удаления записи через DBCalendarService: {calendar_error}")
                return f"Ошибка при отмене записи: {str(calendar_error)}"

            logger.info(f"✅ [CANCEL APPOINTMENT] Запись успешно удалена из БД: appointment_id={appointment_id}")
            
            success_message = f"Ваша запись на {service_name} {date_str} в {time_str} к мастеру {master_name} успешно отменена."
            logger.info(f"🎉 [CANCEL APPOINTMENT] Успешно завершено: {success_message}")
            return success_message
            
        except Exception as e:
            logger.error(f"❌ [CANCEL APPOINTMENT] Критическая ошибка: {str(e)}")
            return f"Ошибка при отмене записи: {str(e)}"

    def reschedule_appointment_by_id(self, appointment_id: int, new_date: str, new_time: str, user_telegram_id: int) -> str:
        """
        Переносит запись на новую дату и время по её ID.
        
        Args:
            appointment_id: ID записи для переноса
            new_date: Новая дата в формате "YYYY-MM-DD"
            new_time: Новое время в формате "HH:MM"
            user_telegram_id: ID пользователя в Telegram для проверки прав доступа
        
        Returns:
            Подтверждение переноса или сообщение об ошибке
        """
        logger.info(f"📅 [RESCHEDULE APPOINTMENT] Начало переноса записи: appointment_id={appointment_id}, user_id={user_telegram_id}, new_date='{new_date}', new_time='{new_time}'")
        
        try:
            # Проверяем права доступа
            appointment = self.appointment_repository.get_by_id(appointment_id)
            if not appointment or appointment['user_telegram_id'] != user_telegram_id:
                logger.warning(f"❌ [RESCHEDULE APPOINTMENT] Нет прав доступа: appointment_id={appointment_id}, user_id={user_telegram_id}, appointment_user_id={appointment['user_telegram_id'] if appointment else 'None'}")
                return "Запись не найдена или у вас нет прав для её переноса."
            
            logger.info(f"✅ [RESCHEDULE APPOINTMENT] Права доступа подтверждены: appointment_id={appointment_id}, user_id={user_telegram_id}")
            
            # Получаем информацию о записи
            master = self.master_repository.get_by_id(appointment['master_id'])
            service = self.service_repository.get_by_id(appointment['service_id'])
            
            if not master or not service:
                logger.warning(f"⚠️ [RESCHEDULE APPOINTMENT] Не найдены данные мастера или услуги для записи {appointment_id}")
                return "Ошибка: не найдены данные о записи."
            
            master_name = self._decode_string_field(master['name'])
            service_name = self._decode_string_field(service['name'])
            start_time = datetime.fromisoformat(appointment['start_time'].replace('Z', '+00:00'))
            old_date_str = start_time.strftime("%d %B")
            old_time_str = start_time.strftime("%H:%M")
            
            logger.info(f"📋 [RESCHEDULE APPOINTMENT] Информация о записи: master='{master_name}', service='{service_name}', old_date='{old_date_str}', old_time='{old_time_str}'")
            
            # Получаем длительность услуги
            duration_minutes = service['duration_minutes']
            logger.info(f"⏱️ [RESCHEDULE APPOINTMENT] Длительность услуги: {duration_minutes} мин")
            
            # Преобразуем новую дату и время в объекты datetime
            try:
                # Парсим дату и время
                appointment_date = datetime.strptime(new_date, "%Y-%m-%d")
                appointment_time = datetime.strptime(new_time, "%H:%M")
                
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
                logger.error(f"❌ [RESCHEDULE APPOINTMENT] Ошибка парсинга даты/времени: {str(e)}")
                return f"Ошибка в формате даты или времени: {str(e)}"
            
            logger.info(f"📅 [RESCHEDULE APPOINTMENT] Новое время записи: {start_datetime} - {end_datetime} (длительность: {duration_minutes} мин)")
            
            # Конвертируем время в формат ISO 8601
            moscow_tz = ZoneInfo('Europe/Moscow')
            start_datetime = start_datetime.replace(tzinfo=moscow_tz)
            end_datetime = end_datetime.replace(tzinfo=moscow_tz)
            
            start_time_iso = start_datetime.strftime('%Y-%m-%dT%H:%M:%S')
            end_time_iso = end_datetime.strftime('%Y-%m-%dT%H:%M:%S')
            
            # Обновляем запись через DBCalendarService
            try:
                logger.info(f"📅 [RESCHEDULE APPOINTMENT] Обновление записи через DBCalendarService: appointment_id={appointment_id}")
                self.db_calendar_service.update_event(
                    appointment_id=appointment_id,
                    new_start_time=start_datetime,
                    new_end_time=end_datetime
                )
                logger.info(f"✅ [RESCHEDULE APPOINTMENT] Запись обновлена через DBCalendarService: appointment_id={appointment_id}")
            except Exception as calendar_error:
                logger.error(f"❌ [RESCHEDULE APPOINTMENT] Ошибка обновления записи через DBCalendarService: {calendar_error}")
                return f"Ошибка при переносе записи: {str(calendar_error)}"

            logger.info(f"✅ [RESCHEDULE APPOINTMENT] Запись успешно обновлена в БД: appointment_id={appointment_id}")
            
            success_message = f"Ваша запись на {service_name} перенесена с {old_date_str} в {old_time_str} на {new_date} в {new_time} к мастеру {master_name}."
            logger.info(f"🎉 [RESCHEDULE APPOINTMENT] Успешно завершено: {success_message}")
            return success_message
            
        except Exception as e:
            logger.error(f"❌ [RESCHEDULE APPOINTMENT] Критическая ошибка: {str(e)}")
            return f"Ошибка при переносе записи: {str(e)}"

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
            decoded_master_name = self._decode_string_field(master['name'])
            if decoded_master_name.lower() == master_name_lower:
                return master
        
        # Затем пробуем нечеткое совпадение
        best_match = None
        best_ratio = 0.0
        
        for master in all_masters:
            decoded_master_name = self._decode_string_field(master['name'])
            # Проверяем совпадение по словам
            master_words = decoded_master_name.lower().split()
            search_words = master_name_lower.split()
            
            # Если хотя бы одно слово совпадает точно
            for search_word in search_words:
                for master_word in master_words:
                    if search_word in master_word or master_word in search_word:
                        return master
            
            # Проверяем общее сходство строк
            ratio = SequenceMatcher(None, master_name_lower, decoded_master_name.lower()).ratio()
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
            decoded_master_name = self._decode_string_field(master['name'])
            master_lower = decoded_master_name.lower()
            
            # Если хотя бы одно ключевое слово есть в имени мастера
            for keyword in keywords:
                if keyword in master_lower and len(keyword) > 2:  # Игнорируем короткие слова
                    similar_masters.append(decoded_master_name)
                    break
        
        # Убираем дубликаты и ограничиваем количество
        return list(set(similar_masters))[:3]
