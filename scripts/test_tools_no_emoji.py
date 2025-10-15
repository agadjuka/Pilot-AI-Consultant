#!/usr/bin/env python3
"""
Тестовый скрипт для проверки всех инструментов ToolService.
Позволяет эмулировать вызовы инструментов, как если бы их делал LLM.
"""

import asyncio
import sys
import os
from dotenv import load_dotenv

# Добавляем корневую директорию проекта в путь
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Загружаем переменные окружения
load_dotenv()

# Импорты после настройки пути
from app.core.database import get_session_local
from app.repositories.client_repository import ClientRepository
from app.repositories.appointment_repository import AppointmentRepository
from app.repositories.master_repository import MasterRepository
from app.repositories.service_repository import ServiceRepository
from app.services.google_calendar_service import GoogleCalendarService
from app.services.appointment_service import AppointmentService
from app.services.tool_service import ToolService


async def main():
    """
    Основная функция для тестирования всех инструментов.
    """
    print("--- ЗАПУСК ПРОВЕРКИ ИНСТРУМЕНТОВ ---")
    print()
    
    # Инициализация всех зависимостей
    print("[ИНИЦИАЛИЗАЦИЯ] Инициализация зависимостей...")
    
    # Создаем сессию базы данных
    SessionLocal = get_session_local()
    db = SessionLocal()
    
    try:
        # Инициализируем все репозитории
        client_repository = ClientRepository(db)
        appointment_repository = AppointmentRepository(db)
        master_repository = MasterRepository(db)
        service_repository = ServiceRepository(db)
        
        # Инициализируем сервисы
        google_calendar_service = GoogleCalendarService()
        appointment_service = AppointmentService(
            appointment_repository=appointment_repository,
            client_repository=client_repository,
            master_repository=master_repository,
            service_repository=service_repository,
            google_calendar_service=google_calendar_service
        )
        
        # Создаем главный объект для теста
        tool_service = ToolService(
            service_repository=service_repository,
            master_repository=master_repository,
            appointment_service=appointment_service,
            google_calendar_service=google_calendar_service
        )
        
        print("[УСПЕХ] Все зависимости инициализированы успешно")
        print()
        
        # Тестовые кейсы для каждого инструмента
        await test_get_all_services(tool_service)
        await test_get_masters_for_service(tool_service)
        await test_get_available_slots(tool_service)
        await test_appointment_workflow(tool_service, client_repository)
        await test_call_manager(tool_service)
        
        print("\n[ЗАВЕРШЕНИЕ] ВСЕ ТЕСТЫ ЗАВЕРШЕНЫ!")
        
    except Exception as e:
        print(f"[ОШИБКА] Критическая ошибка: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


async def test_get_all_services(tool_service):
    """Тест получения всех услуг"""
    print("--- Тест: get_all_services ---")
    try:
        services = tool_service.get_all_services()
        print(f"[УСПЕХ] Результат: {services}")
    except Exception as e:
        print(f"[ОШИБКА] Ошибка: {str(e)}")
    print()


async def test_get_masters_for_service(tool_service):
    """Тест получения мастеров для услуги"""
    print("--- Тест: get_masters_for_service ---")
    
    # Тест с существующей услугой
    try:
        masters = tool_service.get_masters_for_service("Мужская стрижка")
        print(f"[УСПЕХ] Результат для 'Мужская стрижка': {masters}")
    except Exception as e:
        print(f"[ОШИБКА] Ошибка для 'Мужская стрижка': {str(e)}")
    
    # Тест с несуществующей услугой
    try:
        masters_fail = tool_service.get_masters_for_service("Несуществующая услуга")
        print(f"[УСПЕХ] Результат для 'Несуществующая услуга': {masters_fail}")
    except Exception as e:
        print(f"[ОШИБКА] Ошибка для 'Несуществующая услуга': {str(e)}")
    print()


async def test_get_available_slots(tool_service):
    """Тест получения доступных слотов"""
    print("--- Тест: get_available_slots ---")
    
    # Тест успешного получения слотов
    try:
        slots = tool_service.get_available_slots(
            service_name="Мужская стрижка", 
            date="2025-10-25"
        )
        print(f"[УСПЕХ] Результат для 'Мужская стрижка' на 2025-10-25: {slots}")
    except Exception as e:
        print(f"[ОШИБКА] Ошибка для 'Мужская стрижка' на 2025-10-25: {str(e)}")
    
    # Тест с несуществующей услугой
    try:
        slots_fail = tool_service.get_available_slots(
            service_name="Несуществующая услуга", 
            date="2025-10-25"
        )
        print(f"[УСПЕХ] Результат для 'Несуществующая услуга' на 2025-10-25: {slots_fail}")
    except Exception as e:
        print(f"[ОШИБКА] Ошибка для 'Несуществующая услуга' на 2025-10-25: {str(e)}")
    
    # Тест с датой без слотов
    try:
        slots_no_slots = tool_service.get_available_slots(
            service_name="Мужская стрижка", 
            date="2025-10-26"
        )
        print(f"[УСПЕХ] Результат для 'Мужская стрижка' на 2025-10-26: {slots_no_slots}")
    except Exception as e:
        print(f"[ОШИБКА] Ошибка для 'Мужская стрижка' на 2025-10-26: {str(e)}")
    print()


async def test_appointment_workflow(tool_service, client_repository):
    """Тест полного цикла работы с записями"""
    print("--- Тест: Создание, просмотр и отмена записи ---")
    
    # Используем тестовый ID пользователя
    user_id = 261617302
    
    try:
        # Шаг 1: Создание записи
        print("Шаг 1: Создание записи...")
        new_appointment = tool_service.create_appointment(
            master_name="Анна",
            service_name="Чистка лица",
            date="2025-11-10",
            time="14:00",
            client_name="Тестовый клиент",
            user_telegram_id=user_id
        )
        print(f"[УСПЕХ] Результат создания записи: {new_appointment}")
        
        # Шаг 2: Просмотр записей
        print("\nШаг 2: Просмотр записей...")
        my_appointments = tool_service.get_my_appointments(user_telegram_id=user_id)
        print(f"[УСПЕХ] Результат просмотра записей: {my_appointments}")
        
        # Проверяем, что запись была создана
        if my_appointments and len(my_appointments) > 0:
            appointment_to_cancel = my_appointments[0]
            appointment_id = appointment_to_cancel['id']
            
            # Шаг 3: Отмена записи
            print(f"\nШаг 3: Отмена записи с ID {appointment_id}...")
            cancel_result = tool_service.cancel_appointment_by_id(appointment_id=appointment_id)
            print(f"[УСПЕХ] Результат отмены записи: {cancel_result}")
            
            # Шаг 4: Повторный просмотр записей
            print("\nШаг 4: Повторный просмотр записей...")
            my_appointments_after_cancel = tool_service.get_my_appointments(user_telegram_id=user_id)
            print(f"[УСПЕХ] Результат после отмены: {my_appointments_after_cancel}")
            
            # Шаг 5: Тест переноса записи (если есть записи)
            if my_appointments_after_cancel and len(my_appointments_after_cancel) > 0:
                appointment_to_reschedule = my_appointments_after_cancel[0]
                reschedule_id = appointment_to_reschedule['id']
                
                print(f"\nШаг 5: Перенос записи с ID {reschedule_id}...")
                reschedule_result = tool_service.reschedule_appointment_by_id(
                    appointment_id=reschedule_id,
                    new_date="2025-11-15",
                    new_time="16:00"
                )
                print(f"[УСПЕХ] Результат переноса записи: {reschedule_result}")
            else:
                print("\nШаг 5: Нет записей для переноса")
        else:
            print("\n[ПРЕДУПРЕЖДЕНИЕ] Записи не найдены, пропускаем тесты отмены и переноса")
            
    except Exception as e:
        print(f"[ОШИБКА] Ошибка в цикле работы с записями: {str(e)}")
        import traceback
        traceback.print_exc()
    print()


async def test_call_manager(tool_service):
    """Тест вызова менеджера"""
    print("--- Тест: call_manager ---")
    try:
        manager_result = tool_service.call_manager("Тестовая причина вызова менеджера")
        print(f"[УСПЕХ] Результат вызова менеджера: {manager_result}")
    except Exception as e:
        print(f"[ОШИБКА] Ошибка вызова менеджера: {str(e)}")
    print()


if __name__ == "__main__":
    # Запускаем асинхронную функцию
    asyncio.run(main())
