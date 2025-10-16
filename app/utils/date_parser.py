"""
Утилита для парсинга дат в различных форматах.

Этот модуль предоставляет функцию для преобразования строковых представлений дат
в стандартный формат YYYY-MM-DD, используемый в системе.
"""

from datetime import datetime
from typing import Optional
from dateutil import parser
import re


def parse_date_string(date_str: str) -> Optional[str]:
    """
    Парсит строку с датой в различных форматах и возвращает дату в стандартном формате YYYY-MM-DD.
    
    Поддерживаемые форматы:
    - DD.MM.YYYY (например: 15.01.2024)
    - MM/DD/YYYY (например: 01/15/2024)
    - YYYY-MM-DD (например: 2024-01-15)
    - DD-MM-YYYY (например: 15-01-2024)
    - DD месяц YYYY (например: 23 октября 2025)
    - DD месяц (например: 23 октября) - текущий год
    - И многие другие стандартные форматы дат
    
    Args:
        date_str: Строка с датой в любом поддерживаемом формате
        
    Returns:
        Строка с датой в формате YYYY-MM-DD или None, если парсинг не удался
        
    Examples:
        >>> parse_date_string("15.01.2024")
        "2024-01-15"
        >>> parse_date_string("2024-01-15")
        "2024-01-15"
        >>> parse_date_string("23 октября 2025")
        "2025-10-23"
        >>> parse_date_string("23 октября")
        "2025-10-23"  # если текущий год 2025
        >>> parse_date_string("invalid_date")
        None
    """
    if not date_str or not isinstance(date_str, str):
        return None
    
    # Словарь русских названий месяцев
    russian_months = {
        'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4,
        'мая': 5, 'июня': 6, 'июля': 7, 'августа': 8,
        'сентября': 9, 'октября': 10, 'ноября': 11, 'декабря': 12
    }
    
    # Проверяем формат "DD месяц YYYY" или "DD месяц"
    russian_date_pattern = r'(\d{1,2})\s+(' + '|'.join(russian_months.keys()) + r')(?:\s+(\d{4}))?'
    match = re.search(russian_date_pattern, date_str.lower())
    
    if match:
        day = int(match.group(1))
        month_name = match.group(2)
        year = match.group(3)
        
        # Если год не указан, используем текущий год
        if not year:
            year = datetime.now().year
        
        month = russian_months[month_name]
        
        try:
            # Создаем объект datetime
            parsed_date = datetime(int(year), month, day)
            return parsed_date.strftime("%Y-%m-%d")
        except ValueError:
            return None
        
    try:
        # Используем dateutil.parser для гибкого парсинга дат
        parsed_date = parser.parse(date_str, dayfirst=True)
        
        # Форматируем в стандартный формат YYYY-MM-DD
        return parsed_date.strftime("%Y-%m-%d")
        
    except (ValueError, TypeError, OverflowError):
        # Если парсинг не удался, возвращаем None
        return None
