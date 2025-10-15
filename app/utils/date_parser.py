"""
Утилита для парсинга дат в различных форматах.

Этот модуль предоставляет функцию для преобразования строковых представлений дат
в стандартный формат YYYY-MM-DD, используемый в системе.
"""

from datetime import datetime
from typing import Optional
from dateutil import parser


def parse_date_string(date_str: str) -> Optional[str]:
    """
    Парсит строку с датой в различных форматах и возвращает дату в стандартном формате YYYY-MM-DD.
    
    Поддерживаемые форматы:
    - DD.MM.YYYY (например: 15.01.2024)
    - MM/DD/YYYY (например: 01/15/2024)
    - YYYY-MM-DD (например: 2024-01-15)
    - DD-MM-YYYY (например: 15-01-2024)
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
        >>> parse_date_string("invalid_date")
        None
    """
    if not date_str or not isinstance(date_str, str):
        return None
        
    try:
        # Используем dateutil.parser для гибкого парсинга дат
        parsed_date = parser.parse(date_str, dayfirst=True)
        
        # Форматируем в стандартный формат YYYY-MM-DD
        return parsed_date.strftime("%Y-%m-%d")
        
    except (ValueError, TypeError, OverflowError):
        # Если парсинг не удался, возвращаем None
        return None
