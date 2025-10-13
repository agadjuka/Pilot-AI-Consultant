"""
Сервис для форматирования временных слотов в человекочитаемый формат.
"""
from typing import List
from datetime import datetime, timedelta


class SlotFormatter:
    """
    Форматирует список временных слотов в удобный для чтения вид.
    Группирует последовательные слоты в диапазоны.
    """
    
    @staticmethod
    def format_slots_to_ranges(slots: List[str]) -> str:
        """
        Форматирует список слотов в человекочитаемый вид с диапазонами.
        
        Args:
            slots: Список слотов в формате "HH:MM"
        
        Returns:
            Отформатированная строка с диапазонами времени
            
        Examples:
            ['10:00', '10:30', '11:00', '14:30', '15:00'] ->
            "с 10:00 до 11:30, а также с 14:30 до 15:30"
        """
        if not slots:
            return ""
        
        # Преобразуем строки времени в объекты datetime для удобства работы
        time_objects = []
        for slot in slots:
            hour, minute = map(int, slot.split(':'))
            time_obj = datetime(2000, 1, 1, hour, minute)  # Дата фиктивная
            time_objects.append(time_obj)
        
        # Группируем последовательные слоты (шаг 30 минут)
        ranges = []
        current_range_start = time_objects[0]
        current_range_end = time_objects[0]
        
        for i in range(1, len(time_objects)):
            # Проверяем, является ли текущий слот продолжением предыдущего
            expected_next = current_range_end + timedelta(minutes=30)
            if time_objects[i] == expected_next:
                # Продолжаем текущий диапазон
                current_range_end = time_objects[i]
            else:
                # Завершаем текущий диапазон и начинаем новый
                ranges.append((current_range_start, current_range_end))
                current_range_start = time_objects[i]
                current_range_end = time_objects[i]
        
        # Добавляем последний диапазон
        ranges.append((current_range_start, current_range_end))
        
        # Форматируем диапазоны в строку
        formatted_ranges = []
        for start, end in ranges:
            start_str = start.strftime("%H:%M")
            # Конец диапазона - это начало следующего слота (+ 30 минут)
            end_str = (end + timedelta(minutes=30)).strftime("%H:%M")
            
            if start == end:
                # Одиночный слот
                formatted_ranges.append(f"в {start_str}")
            else:
                # Диапазон
                formatted_ranges.append(f"с {start_str} до {end_str}")
        
        # Объединяем диапазоны в читаемую строку
        if len(formatted_ranges) == 1:
            return formatted_ranges[0]
        elif len(formatted_ranges) == 2:
            return f"{formatted_ranges[0]} и {formatted_ranges[1]}"
        else:
            # Для трех и более диапазонов
            last = formatted_ranges[-1]
            others = ", ".join(formatted_ranges[:-1])
            return f"{others}, а также {last}"

