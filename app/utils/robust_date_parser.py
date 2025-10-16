"""
Надежный парсер дат с множественными fallback механизмами.

Этот модуль предоставляет максимально надежную систему парсинга дат,
которая обрабатывает все возможные форматы и вариации, включая ошибки нейронки.
"""

from datetime import datetime, timedelta
from typing import Optional, Tuple, List, Dict, Any
from dateutil import parser
import re
import logging

logger = logging.getLogger(__name__)


class RobustDateParser:
    """
    Надежный парсер дат с множественными стратегиями обработки.
    
    Обрабатывает:
    - Стандартные форматы дат
    - Русские названия месяцев и дней недели
    - Относительные даты (завтра, послезавтра, через неделю)
    - Частичные даты (только день, только месяц)
    - Ошибки нейронки (неправильные форматы)
    - Нечеткие совпадения
    """
    
    def __init__(self):
        """Инициализирует парсер с настройками."""
        self.russian_months = {
            'января': 1, 'февраля': 2, 'марта': 3, 'апреля': 4,
            'мая': 5, 'июня': 6, 'июля': 7, 'августа': 8,
            'сентября': 9, 'октября': 10, 'ноября': 11, 'декабря': 12,
            'январь': 1, 'февраль': 2, 'март': 3, 'апрель': 4,
            'май': 5, 'июнь': 6, 'июль': 7, 'август': 8,
            'сентябрь': 9, 'октябрь': 10, 'ноябрь': 11, 'декабрь': 12,
            'янв': 1, 'фев': 2, 'мар': 3, 'апр': 4,
            'май': 5, 'июн': 6, 'июл': 7, 'авг': 8,
            'сен': 9, 'окт': 10, 'ноя': 11, 'дек': 12
        }
        
        self.russian_days = {
            'понедельник': 0, 'вторник': 1, 'среда': 2, 'четверг': 3,
            'пятница': 4, 'суббота': 5, 'воскресенье': 6,
            'пн': 0, 'вт': 1, 'ср': 2, 'чт': 3, 'пт': 4, 'сб': 5, 'вс': 6
        }
        
        self.relative_dates = {
            'сегодня': 0, 'завтра': 1, 'послезавтра': 2,
            'через неделю': 7, 'через месяц': 30
        }
        
        # Паттерны для различных форматов дат
        self.date_patterns = [
            # DD.MM.YYYY
            r'(\d{1,2})\.(\d{1,2})\.(\d{4})',
            # DD/MM/YYYY
            r'(\d{1,2})/(\d{1,2})/(\d{4})',
            # YYYY-MM-DD
            r'(\d{4})-(\d{1,2})-(\d{1,2})',
            # DD-MM-YYYY
            r'(\d{1,2})-(\d{1,2})-(\d{4})',
            # DD месяц YYYY
            r'(\d{1,2})\s+(' + '|'.join(self.russian_months.keys()) + r')(?:\s+(\d{4}))?',
            # день недели, DD месяц YYYY (как в логах)
            r'(' + '|'.join(self.russian_days.keys()) + r'),?\s+(\d{1,2})\.(\d{1,2})\.(\d{4})',
            # день недели DD месяц YYYY
            r'(' + '|'.join(self.russian_days.keys()) + r'),?\s+(\d{1,2})\s+(' + '|'.join(self.russian_months.keys()) + r')(?:\s+(\d{4}))?',
        ]
    
    def parse_date(self, date_str: str, reference_date: Optional[datetime] = None) -> Optional[str]:
        """
        Основной метод парсинга даты с множественными fallback стратегиями.
        
        Args:
            date_str: Строка с датой
            reference_date: Опорная дата для относительных дат (по умолчанию - сегодня)
            
        Returns:
            Дата в формате YYYY-MM-DD или None
        """
        if not date_str or not isinstance(date_str, str):
            return None
            
        if reference_date is None:
            reference_date = datetime.now()
            
        date_str = date_str.strip().lower()
        
        # Стратегия 1: Относительные даты
        result = self._parse_relative_date(date_str, reference_date)
        if result:
            logger.debug(f"Относительная дата распознана: {date_str} -> {result}")
            return result
        
        # Стратегия 2: Русские форматы с днями недели
        result = self._parse_russian_with_weekday(date_str, reference_date)
        if result:
            logger.debug(f"Русский формат с днем недели: {date_str} -> {result}")
            return result
        
        # Стратегия 3: Стандартные паттерны
        result = self._parse_patterns(date_str)
        if result:
            logger.debug(f"Стандартный паттерн: {date_str} -> {result}")
            return result
        
        # Стратегия 4: dateutil.parser с настройками
        result = self._parse_with_dateutil(date_str)
        if result:
            logger.debug(f"dateutil.parser: {date_str} -> {result}")
            return result
        
        # Стратегия 5: Нечеткий поиск и исправление
        result = self._fuzzy_parse(date_str, reference_date)
        if result:
            logger.debug(f"Нечеткий парсинг: {date_str} -> {result}")
            return result
        
        logger.warning(f"Не удалось распарсить дату: {date_str}")
        return None
    
    def _parse_relative_date(self, date_str: str, reference_date: datetime) -> Optional[str]:
        """Парсинг относительных дат (завтра, послезавтра и т.д.)."""
        for relative, days in self.relative_dates.items():
            if relative in date_str:
                target_date = reference_date + timedelta(days=days)
                return target_date.strftime("%Y-%m-%d")
        return None
    
    def _parse_russian_with_weekday(self, date_str: str, reference_date: datetime) -> Optional[str]:
        """Парсинг русских форматов с днями недели."""
        # Паттерн: "Пятница, 17.10.2025" или "Пятница 17.10.2025"
        weekday_pattern = r'(' + '|'.join(self.russian_days.keys()) + r'),?\s+(\d{1,2})\.(\d{1,2})\.(\d{4})'
        match = re.search(weekday_pattern, date_str)
        
        if match:
            weekday_name = match.group(1)
            day = int(match.group(2))
            month = int(match.group(3))
            year = int(match.group(4))
            
            try:
                parsed_date = datetime(year, month, day)
                return parsed_date.strftime("%Y-%m-%d")
            except ValueError:
                pass
        
        # Паттерн: "Пятница, 17 октября 2025" или "Пятница 17 октября 2025"
        weekday_month_pattern = r'(' + '|'.join(self.russian_days.keys()) + r'),?\s+(\d{1,2})\s+(' + '|'.join(self.russian_months.keys()) + r')(?:\s+(\d{4}))?'
        match = re.search(weekday_month_pattern, date_str)
        
        if match:
            weekday_name = match.group(1)
            day = int(match.group(2))
            month_name = match.group(3)
            year = match.group(4)
            
            if not year:
                year = reference_date.year
            
            month = self.russian_months[month_name]
            
            try:
                parsed_date = datetime(int(year), month, day)
                return parsed_date.strftime("%Y-%m-%d")
            except ValueError:
                pass
        
        # Паттерн: "17 октября 2025" (без дня недели)
        month_pattern = r'(\d{1,2})\s+(' + '|'.join(self.russian_months.keys()) + r')(?:\s+(\d{4}))?'
        match = re.search(month_pattern, date_str)
        
        if match:
            day = int(match.group(1))
            month_name = match.group(2)
            year = match.group(3)
            
            if not year:
                year = reference_date.year
            
            month = self.russian_months[month_name]
            
            try:
                parsed_date = datetime(int(year), month, day)
                return parsed_date.strftime("%Y-%m-%d")
            except ValueError:
                pass
        
        # Паттерн: "октябрь 17 2025" (месяц день год)
        month_day_year_pattern = r'(' + '|'.join(self.russian_months.keys()) + r')\s+(\d{1,2})(?:\s+(\d{4}))?'
        match = re.search(month_day_year_pattern, date_str)
        
        if match:
            month_name = match.group(1)
            day = int(match.group(2))
            year = match.group(3)
            
            if not year:
                year = reference_date.year
            
            month = self.russian_months[month_name]
            
            try:
                parsed_date = datetime(int(year), month, day)
                return parsed_date.strftime("%Y-%m-%d")
            except ValueError:
                pass
        
        return None
    
    def _parse_patterns(self, date_str: str) -> Optional[str]:
        """Парсинг стандартных паттернов дат."""
        for pattern in self.date_patterns:
            match = re.search(pattern, date_str)
            if match:
                groups = match.groups()
                
                # Обработка различных форматов
                if len(groups) == 3:
                    # DD.MM.YYYY или DD/MM/YYYY
                    if '.' in date_str:
                        day, month, year = groups
                    elif '/' in date_str:
                        month, day, year = groups  # Американский формат
                    else:
                        day, month, year = groups
                    
                    try:
                        parsed_date = datetime(int(year), int(month), int(day))
                        return parsed_date.strftime("%Y-%m-%d")
                    except ValueError:
                        continue
                
                elif len(groups) == 4:
                    # YYYY-MM-DD
                    year, month, day = groups[:3]
                    try:
                        parsed_date = datetime(int(year), int(month), int(day))
                        return parsed_date.strftime("%Y-%m-%d")
                    except ValueError:
                        continue
        
        return None
    
    def _parse_with_dateutil(self, date_str: str) -> Optional[str]:
        """Парсинг с помощью dateutil.parser с различными настройками."""
        # Пробуем разные настройки парсера
        settings_variants = [
            {'dayfirst': True},
            {'dayfirst': False},
            {'dayfirst': True, 'yearfirst': False},
            {'dayfirst': False, 'yearfirst': True},
        ]
        
        for settings in settings_variants:
            try:
                parsed_date = parser.parse(date_str, **settings)
                return parsed_date.strftime("%Y-%m-%d")
            except (ValueError, TypeError, OverflowError):
                continue
        
        return None
    
    def _fuzzy_parse(self, date_str: str, reference_date: datetime) -> Optional[str]:
        """Нечеткий парсинг с попытками исправления."""
        # Удаляем лишние символы и пробелы
        cleaned = re.sub(r'[^\d\w\s\.\-\/]', '', date_str).strip()
        
        # Пробуем исправить очевидные ошибки
        corrections = [
            # Заменяем запятые на точки
            (r',', '.'),
            # Исправляем двойные точки
            (r'\.\.', '.'),
            # Исправляем пробелы в датах
            (r'(\d)\s+(\d)', r'\1\2'),
        ]
        
        for pattern, replacement in corrections:
            cleaned = re.sub(pattern, replacement, cleaned)
        
        # Пробуем парсить исправленную строку
        if cleaned != date_str:
            result = self._parse_patterns(cleaned)
            if result:
                return result
        
        # Пробуем извлечь числа и составить дату
        numbers = re.findall(r'\d+', date_str)
        if len(numbers) >= 2:
            # Пробуем разные комбинации
            for day, month in [(int(numbers[0]), int(numbers[1])), (int(numbers[1]), int(numbers[0]))]:
                if 1 <= day <= 31 and 1 <= month <= 12:
                    year = reference_date.year
                    if len(numbers) >= 3:
                        year = int(numbers[2])
                        if year < 100:  # Двухзначный год
                            year += 2000 if year < 50 else 1900
                    
                    try:
                        parsed_date = datetime(year, month, day)
                        return parsed_date.strftime("%Y-%m-%d")
                    except ValueError:
                        continue
        
        return None
    
    def parse_date_with_fallback(self, date_str: str, reference_date: Optional[datetime] = None) -> Tuple[Optional[str], Dict[str, Any]]:
        """
        Парсинг даты с подробной информацией о процессе и fallback стратегиях.
        
        Args:
            date_str: Строка с датой
            reference_date: Опорная дата
            
        Returns:
            Кортеж (результат, метаданные)
        """
        metadata = {
            'original_input': date_str,
            'success': False,
            'method_used': None,
            'attempts': [],
            'errors': []
        }
        
        if reference_date is None:
            reference_date = datetime.now()
        
        # Стратегия 1: Относительные даты
        try:
            result = self._parse_relative_date(date_str, reference_date)
            metadata['attempts'].append('relative_date')
            if result:
                metadata['success'] = True
                metadata['method_used'] = 'relative_date'
                return result, metadata
        except Exception as e:
            metadata['errors'].append(f'relative_date: {str(e)}')
        
        # Стратегия 2: Русские форматы
        try:
            result = self._parse_russian_with_weekday(date_str, reference_date)
            metadata['attempts'].append('russian_weekday')
            if result:
                metadata['success'] = True
                metadata['method_used'] = 'russian_weekday'
                return result, metadata
        except Exception as e:
            metadata['errors'].append(f'russian_weekday: {str(e)}')
        
        # Стратегия 3: Стандартные паттерны
        try:
            result = self._parse_patterns(date_str)
            metadata['attempts'].append('patterns')
            if result:
                metadata['success'] = True
                metadata['method_used'] = 'patterns'
                return result, metadata
        except Exception as e:
            metadata['errors'].append(f'patterns: {str(e)}')
        
        # Стратегия 4: dateutil
        try:
            result = self._parse_with_dateutil(date_str)
            metadata['attempts'].append('dateutil')
            if result:
                metadata['success'] = True
                metadata['method_used'] = 'dateutil'
                return result, metadata
        except Exception as e:
            metadata['errors'].append(f'dateutil: {str(e)}')
        
        # Стратегия 5: Нечеткий поиск
        try:
            result = self._fuzzy_parse(date_str, reference_date)
            metadata['attempts'].append('fuzzy')
            if result:
                metadata['success'] = True
                metadata['method_used'] = 'fuzzy'
                return result, metadata
        except Exception as e:
            metadata['errors'].append(f'fuzzy: {str(e)}')
        
        return None, metadata


# Глобальный экземпляр парсера
_parser_instance = RobustDateParser()


def parse_date_robust(date_str: str, reference_date: Optional[datetime] = None) -> Optional[str]:
    """
    Удобная функция для парсинга дат с максимальной надежностью.
    
    Args:
        date_str: Строка с датой
        reference_date: Опорная дата
        
    Returns:
        Дата в формате YYYY-MM-DD или None
    """
    return _parser_instance.parse_date(date_str, reference_date)


def parse_date_with_metadata(date_str: str, reference_date: Optional[datetime] = None) -> Tuple[Optional[str], Dict[str, Any]]:
    """
    Парсинг даты с подробными метаданными для отладки.
    
    Args:
        date_str: Строка с датой
        reference_date: Опорная дата
        
    Returns:
        Кортеж (результат, метаданные)
    """
    return _parser_instance.parse_date_with_fallback(date_str, reference_date)


def validate_date_format(date_str: str) -> bool:
    """
    Проверяет, является ли строка валидной датой в формате YYYY-MM-DD.
    
    Args:
        date_str: Строка для проверки
        
    Returns:
        True если строка является валидной датой
    """
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False
