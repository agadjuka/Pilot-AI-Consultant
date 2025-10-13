"""
Скрипт для реалистичного заполнения Google Calendar тестовыми записями.
Создает различные сценарии загрузки мастеров для тестирования бота.
"""
import random
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import sys
import os
from pathlib import Path

# Добавляем корневую директорию проекта в PYTHONPATH
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Устанавливаем переменную окружения для загрузки .env
os.chdir(project_root)

from app.core.database import get_session_local
from app.repositories.master_repository import MasterRepository
from app.repositories.service_repository import ServiceRepository

# Прямой импорт модуля без __init__.py
import importlib.util
spec = importlib.util.spec_from_file_location(
    "google_calendar_service",
    project_root / "app" / "services" / "google_calendar_service.py"
)
google_calendar_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(google_calendar_module)
GoogleCalendarService = google_calendar_module.GoogleCalendarService


class RealisticCalendarSeeder:
    """Класс для создания реалистичного календаря салона красоты."""
    
    def __init__(self):
        """Инициализация седера."""
        self.db = get_session_local()()
        self.calendar_service = GoogleCalendarService()
        self.master_repo = MasterRepository(self.db)
        self.service_repo = ServiceRepository(self.db)
        self.moscow_tz = ZoneInfo('Europe/Moscow')
        
        # Рабочие часы салона
        self.WORK_START_HOUR = 10
        self.WORK_END_HOUR = 20
        
        # Загружаем данные из БД
        self.masters = self.master_repo.get_all()
        self.services = self.service_repo.get_all()
        
        print(f"✓ Загружено мастеров: {len(self.masters)}")
        print(f"✓ Загружено услуг: {len(self.services)}")
    
    def generate_realistic_schedule(self, start_date: datetime, days: int = 30):
        """
        Генерирует реалистичное расписание на указанное количество дней.
        
        Args:
            start_date: Начальная дата
            days: Количество дней для заполнения
        """
        print(f"\n📅 Генерация реалистичного расписания на {days} дней")
        print(f"   Период: {start_date.strftime('%d.%m.%Y')} - {(start_date + timedelta(days=days)).strftime('%d.%m.%Y')}")
        
        total_created = 0
        
        for day_offset in range(days):
            current_date = start_date + timedelta(days=day_offset)
            day_created = self._fill_day_realistic(current_date, day_offset)
            total_created += day_created
            
            if day_offset % 7 == 0:  # Каждую неделю показываем прогресс
                print(f"   Прогресс: {day_offset + 1}/{days} дней, создано записей: {total_created}")
        
        print(f"✅ Всего создано записей: {total_created}")
        return total_created
    
    def _fill_day_realistic(self, date: datetime, day_offset: int) -> int:
        """
        Заполняет один день реалистичными записями.
        
        Args:
            date: Дата для заполнения
            day_offset: Смещение от начальной даты (для определения сценария)
        
        Returns:
            int: Количество созданных записей
        """
        created_count = 0
        
        # Определяем сценарий загрузки в зависимости от дня
        scenario = self._get_day_scenario(day_offset)
        
        for master in self.masters:
            master_scenario = self._get_master_scenario(master, day_offset, scenario)
            master_records = self._create_master_records(date, master, master_scenario)
            created_count += master_records
        
        return created_count
    
    def _get_day_scenario(self, day_offset: int) -> str:
        """
        Определяет общий сценарий загрузки для дня.
        
        Args:
            day_offset: Смещение от начальной даты
        
        Returns:
            str: Тип сценария ('busy', 'normal', 'light', 'free')
        """
        if day_offset < 3:
            # Первые 3 дня - очень загруженные
            return 'busy'
        elif day_offset < 7:
            # Следующие 4 дня - нормальная загрузка
            return 'normal'
        elif day_offset < 14:
            # Следующая неделя - легкая загрузка
            return 'light'
        else:
            # Остальные дни - свободные
            return 'free'
    
    def _get_master_scenario(self, master, day_offset: int, day_scenario: str) -> dict:
        """
        Определяет сценарий загрузки для конкретного мастера.
        
        Args:
            master: Объект мастера
            day_offset: Смещение от начальной даты
            day_scenario: Общий сценарий дня
        
        Returns:
            dict: Параметры сценария для мастера
        """
        # Добавляем индивидуальность мастеров
        master_id = master.id
        
        # Некоторые мастера всегда более загружены
        if master_id in [1, 3, 5]:  # Популярные мастера
            busy_factor = 1.3
        elif master_id in [2, 4]:  # Средняя популярность
            busy_factor = 1.0
        else:  # Менее популярные мастера
            busy_factor = 0.7
        
        # Определяем количество записей в зависимости от сценария дня
        if day_scenario == 'busy':
            base_records = random.randint(6, 8)
        elif day_scenario == 'normal':
            base_records = random.randint(3, 5)
        elif day_scenario == 'light':
            base_records = random.randint(1, 3)
        else:  # free
            base_records = random.randint(0, 1)
        
        # Применяем фактор популярности мастера
        records_count = max(0, int(base_records * busy_factor))
        
        # Иногда мастер может быть полностью свободен
        if random.random() < 0.1:  # 10% шанс
            records_count = 0
        
        return {
            'records_count': records_count,
            'busy_factor': busy_factor,
            'scenario': day_scenario
        }
    
    def _create_master_records(self, date: datetime, master, scenario: dict) -> int:
        """
        Создает записи для мастера на указанную дату.
        
        Args:
            date: Дата
            master: Объект мастера
            scenario: Сценарий загрузки
        
        Returns:
            int: Количество созданных записей
        """
        records_count = scenario['records_count']
        if records_count == 0:
            return 0
        
        created = 0
        
        # Генерируем временные слоты для мастера
        time_slots = self._generate_time_slots(date, records_count)
        
        for i, slot in enumerate(time_slots):
            # Выбираем случайную услугу
            service = random.choice(self.services)
            
            # Создаем запись
            start_time = slot['start']
            end_time = slot['end']
            
            try:
                # Используем новый метод create_event
                success = self.calendar_service.create_event(
                    master_name=master.name,
                    service_name=service.name,
                    start_time_iso=start_time.isoformat(),
                    end_time_iso=end_time.isoformat()
                )
                
                if success:
                    created += 1
                    print(f"    ✓ {master.name}: {start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')} ({service.name})")
                
            except Exception as e:
                print(f"    ❌ Ошибка при создании записи для {master.name}: {str(e)}")
        
        return created
    
    def _generate_time_slots(self, date: datetime, count: int) -> list:
        """
        Генерирует временные слоты для записей.
        
        Args:
            date: Дата
            count: Количество слотов
        
        Returns:
            list: Список словарей с временными слотами
        """
        slots = []
        
        # Создаем список всех возможных временных интервалов
        possible_times = []
        current_time = date.replace(
            hour=self.WORK_START_HOUR,
            minute=0,
            second=0,
            microsecond=0,
            tzinfo=self.moscow_tz
        )
        
        work_end = date.replace(
            hour=self.WORK_END_HOUR,
            minute=0,
            second=0,
            microsecond=0,
            tzinfo=self.moscow_tz
        )
        
        # Генерируем возможные времена с шагом 30 минут
        while current_time < work_end:
            possible_times.append(current_time)
            current_time += timedelta(minutes=30)
        
        # Выбираем случайные времена, избегая пересечений
        used_times = set()
        
        for _ in range(count):
            # Выбираем случайное время
            attempts = 0
            while attempts < 20:  # Максимум 20 попыток
                start_time = random.choice(possible_times)
                
                # Проверяем, не пересекается ли с уже выбранными
                is_conflict = False
                for used_start in used_times:
                    if abs((start_time - used_start).total_seconds()) < 3600:  # Меньше часа разницы
                        is_conflict = True
                        break
                
                if not is_conflict:
                    used_times.add(start_time)
                    
                    # Выбираем случайную услугу для определения длительности
                    service = random.choice(self.services)
                    duration_minutes = service.duration_minutes
                    
                    end_time = start_time + timedelta(minutes=duration_minutes)
                    
                    # Проверяем, что запись не выходит за рабочие часы
                    if end_time <= work_end:
                        slots.append({
                            'start': start_time,
                            'end': end_time,
                            'service': service
                        })
                    break
                
                attempts += 1
        
        return slots
    
    def clear_existing_records(self, start_date: datetime, days: int = 30):
        """
        Очищает существующие записи в указанном периоде.
        
        Args:
            start_date: Начальная дата
            days: Количество дней
        """
        end_date = start_date + timedelta(days=days)
        
        print(f"\n🧹 Очистка существующих записей...")
        print(f"   Период: {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}")
        
        deleted_count = self.calendar_service.clear_calendar(
            time_min=start_date,
            time_max=end_date
        )
        
        print(f"✓ Удалено событий: {deleted_count}")
        return deleted_count
    
    def run(self):
        """Запускает процесс заполнения календаря."""
        print("=" * 70)
        print("🎨 ЗАПОЛНЕНИЕ КАЛЕНДАРЯ РЕАЛИСТИЧНЫМИ ДАННЫМИ")
        print("=" * 70)
        
        # Определяем период заполнения (следующие 30 дней)
        now = datetime.now(self.moscow_tz)
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        try:
            # Очищаем существующие записи
            self.clear_existing_records(start_date, 30)
            
            # Заполняем календарь реалистичными данными
            total_created = self.generate_realistic_schedule(start_date, 30)
            
            print("\n" + "=" * 70)
            print("✅ ЗАПОЛНЕНИЕ КАЛЕНДАРЯ ЗАВЕРШЕНО!")
            print(f"📊 Всего создано записей: {total_created}")
            print("🎯 Сценарии загрузки:")
            print("   • Дни 1-3: Очень загруженные (6-8 записей на мастера)")
            print("   • Дни 4-7: Нормальная загрузка (3-5 записей)")
            print("   • Дни 8-14: Легкая загрузка (1-3 записи)")
            print("   • Дни 15-30: Свободные дни (0-1 запись)")
            print("=" * 70)
            
        except Exception as e:
            print(f"\n❌ Критическая ошибка: {str(e)}")
            raise
        finally:
            self.db.close()


def main():
    """Главная функция для запуска скрипта."""
    seeder = RealisticCalendarSeeder()
    seeder.run()


if __name__ == "__main__":
    main()
