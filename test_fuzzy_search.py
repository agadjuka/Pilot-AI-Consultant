#!/usr/bin/env python3
"""
Тест для проверки нечеткого поиска услуг
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.tool_service import ToolService
from app.repositories.service_repository import ServiceRepository
from app.repositories.master_repository import MasterRepository
from app.services.google_calendar_service import GoogleCalendarService

def test_fuzzy_search():
    """Тестирует нечеткий поиск услуг"""
    
    # Создаем экземпляры сервисов
    service_repo = ServiceRepository()
    master_repo = MasterRepository()
    calendar_service = GoogleCalendarService()
    
    tool_service = ToolService(service_repo, master_repo, calendar_service)
    
    print("=== ТЕСТ НЕЧЕТКОГО ПОИСКА УСЛУГ ===\n")
    
    # Тестовые случаи
    test_cases = [
        "ламинирование бровей",  # Не существует, должно предложить альтернативы
        "ламинирование ресниц",  # Существует точно
        "стрижка",              # Частичное совпадение
        "окрашивание",          # Частичное совпадение
        "маникюр",              # Частичное совпадение
        "бровей",               # Только ключевое слово
        "несуществующая услуга" # Полностью несуществующая
    ]
    
    for test_case in test_cases:
        print(f"🔍 Поиск: '{test_case}'")
        result = tool_service.get_masters_for_service(test_case)
        print(f"📋 Результат: {result}")
        print("-" * 80)

if __name__ == "__main__":
    test_fuzzy_search()
