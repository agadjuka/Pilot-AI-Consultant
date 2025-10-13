"""
Тестовый скрипт для проверки работы поиска свободных слотов.
"""
from datetime import datetime, timedelta
from app.services.google_calendar_service import GoogleCalendarService


def test_free_slots():
    """
    Тестирует поиск свободных слотов для мастеров на разные даты.
    """
    print("\n" + "="*60)
    print("   🧪 Тестирование поиска свободных слотов")
    print("="*60 + "\n")
    
    # Инициализируем сервис
    calendar_service = GoogleCalendarService()
    
    # Определяем даты для тестирования
    today = datetime.now()
    tomorrow = today + timedelta(days=1)
    day_after_tomorrow = today + timedelta(days=2)
    
    test_dates = [
        today.strftime("%Y-%m-%d"),
        tomorrow.strftime("%Y-%m-%d"),
        day_after_tomorrow.strftime("%Y-%m-%d")
    ]
    
    # Список мастеров для тестирования
    masters = ["Анна", "Мария", "Ольга"]
    
    # Тестируем для каждого мастера и даты
    for master in masters:
        print(f"\n📋 Мастер: {master}")
        print("-" * 60)
        
        for date in test_dates:
            try:
                free_slots = calendar_service.get_free_slots(master, date)
                
                if free_slots:
                    print(f"  ✅ {date}: найдено {len(free_slots)} свободных слотов")
                    print(f"     Слоты: {', '.join(free_slots[:5])}{'...' if len(free_slots) > 5 else ''}")
                else:
                    print(f"  ⚠️  {date}: нет свободных слотов")
                    
            except Exception as e:
                print(f"  ❌ {date}: ошибка - {str(e)}")
    
    print("\n" + "="*60)
    print("   ✅ Тестирование завершено")
    print("="*60 + "\n")


if __name__ == "__main__":
    test_free_slots()

