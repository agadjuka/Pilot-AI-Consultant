"""
Централизованная конфигурация логирования для приложения.
Обеспечивает единообразное форматирование и цветовое выделение логов.
"""

import logging
import sys
from typing import Optional


class ColoredFormatter(logging.Formatter):
    """
    Кастомный форматер с цветовым выделением уровней логирования.
    """
    
    # ANSI коды цветов
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m'        # Reset
    }
    
    # Символы для уровней
    LEVEL_SYMBOLS = {
        'DEBUG': '🔍',
        'INFO': 'ℹ️',
        'WARNING': '⚠️',
        'ERROR': '❌',
        'CRITICAL': '🚨'
    }
    
    def format(self, record):
        # Получаем цвет для уровняя
        color = self.COLORS.get(record.levelname, self.COLORS['RESET'])
        reset = self.COLORS['RESET']
        symbol = self.LEVEL_SYMBOLS.get(record.levelname, '📝')
        
        # Форматируем время
        timestamp = self.formatTime(record, self.datefmt)
        
        # Форматируем сообщение с цветом
        colored_level = f"{color}{record.levelname}{reset}"
        colored_symbol = f"{color}{symbol}{reset}"
        
        # Создаем красивое форматирование
        formatted_message = (
            f"{colored_symbol} {timestamp} | "
            f"{colored_level:8} | "
            f"{record.name:20} | "
            f"{record.getMessage()}"
        )
        
        return formatted_message


class DialogFormatter(logging.Formatter):
    """
    Специальный форматер для диалоговых сообщений с рамками.
    """
    
    def format(self, record):
        # Получаем базовое сообщение
        message = record.getMessage()
        
        # Если сообщение начинается с символов рамки, форматируем его
        if message.startswith('╔') or message.startswith('║') or message.startswith('╚'):
            # Добавляем цвет для рамок
            if message.startswith('╔'):
                return f"\033[34m{message}\033[0m"  # Синий для верхней границы
            elif message.startswith('║'):
                return f"\033[36m{message}\033[0m"  # Cyan для содержимого
            elif message.startswith('╚'):
                return f"\033[34m{message}\033[0m"  # Синий для нижней границы
        
        # Для обычных сообщений используем стандартное форматирование
        return super().format(record)


def setup_logging(level: str = "INFO", enable_colors: bool = True, suppress_ydb_tokens: bool = True) -> None:
    """
    Настраивает централизованное логирование для всего приложения.
    
    Args:
        level: Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        enable_colors: Включить цветовое выделение в консоли
        suppress_ydb_tokens: Подавлять сообщения YDB о токенах (по умолчанию True)
    """
    # Получаем корневой логгер
    root_logger = logging.getLogger()
    
    # Очищаем существующие обработчики
    root_logger.handlers.clear()
    
    # Устанавливаем уровень логирования
    log_level = getattr(logging, level.upper(), logging.INFO)
    root_logger.setLevel(log_level)
    
    # Создаем обработчик для консоли
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    
    # Выбираем форматер в зависимости от настроек
    if enable_colors and sys.stdout.isatty():
        # Используем цветной форматер для терминала
        formatter = ColoredFormatter(
            fmt='%(message)s',
            datefmt='%H:%M:%S'
        )
    else:
        # Простой форматер для файлов или не-терминалов
        formatter = logging.Formatter(
            fmt='%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s',
            datefmt='%H:%M:%S'
        )
    
    console_handler.setFormatter(formatter)
    
    # Добавляем обработчик к корневому логгеру
    root_logger.addHandler(console_handler)
    
    # Настраиваем уровни для конкретных модулей
    _configure_module_levels(suppress_ydb_tokens)
    
    # Логируем успешную настройку
    logger = logging.getLogger(__name__)
    logger.info("╔═══════════════════════════════════════════════════════════")
    logger.info("║ 🎨 Система логирования инициализирована")
    logger.info(f"║ 📊 Уровень логирования: {level}")
    logger.info(f"║ 🌈 Цветовое выделение: {'включено' if enable_colors else 'отключено'}")
    logger.info(f"║ 🔇 Подавление YDB токенов: {'включено' if suppress_ydb_tokens else 'отключено'}")
    logger.info("╚═══════════════════════════════════════════════════════════")


def _configure_module_levels(suppress_ydb_tokens: bool = True):
    """
    Настраивает уровни логирования для конкретных модулей.
    
    Args:
        suppress_ydb_tokens: Подавлять сообщения YDB о токенах
    """
    # Уменьшаем уровень логирования для внешних библиотек
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('google').setLevel(logging.WARNING)
    
    # Подавляем сообщения YDB SDK о токенах (если включено)
    if suppress_ydb_tokens:
        logging.getLogger('ydb.credentials.MetadataUrlCredentials').setLevel(logging.ERROR)
        logging.getLogger('ydb.credentials.ServiceAccountCredentials').setLevel(logging.ERROR)
        logging.getLogger('ydb.credentials').setLevel(logging.ERROR)
        logging.getLogger('ydb').setLevel(logging.WARNING)
    
    # Настраиваем уровень для наших модулей
    logging.getLogger('app.services.dialog_service').setLevel(logging.DEBUG)
    logging.getLogger('app.services.tool_service').setLevel(logging.DEBUG)
    logging.getLogger('app.services.classification_service').setLevel(logging.DEBUG)


def get_logger(name: str) -> logging.Logger:
    """
    Получает логгер с указанным именем.
    
    Args:
        name: Имя логгера (обычно __name__)
        
    Returns:
        Настроенный логгер
    """
    return logging.getLogger(name)


def log_dialog_start(logger: logging.Logger, user_id: int, message: str) -> None:
    """
    Логирует начало обработки диалога с красивым форматированием.
    
    Args:
        logger: Логгер для записи
        user_id: ID пользователя
        message: Сообщение пользователя
    """
    logger.info("╔═══════════════════════════════════════════════════════════")
    logger.info("║ 🚀 Начало обработки сообщения")
    logger.info(f"║ 👤 Пользователь: {user_id}")
    logger.info(f"║ 💬 Сообщение: '{message}'")
    logger.info("╚═══════════════════════════════════════════════════════════")


def log_dialog_end(logger: logging.Logger, response: str) -> None:
    """
    Логирует завершение обработки диалога.
    
    Args:
        logger: Логгер для записи
        response: Ответ бота
    """
    logger.info("╔═══════════════════════════════════════════════════════════")
    logger.info("║ ✅ Обработка завершена")
    logger.info(f"║ 🤖 Ответ бота: '{response}'")
    logger.info("╚═══════════════════════════════════════════════════════════\n")


def log_error(logger: logging.Logger, error: Exception, context: str = "") -> None:
    """
    Логирует ошибку с полным стеком и контекстом.
    
    Args:
        logger: Логгер для записи
        error: Исключение
        context: Дополнительный контекст
    """
    logger.error("╔═══════════════════════════════════════════════════════════")
    logger.error("║ ❌ ОШИБКА ОБРАБОТКИ")
    if context:
        logger.error(f"║ 📍 Контекст: {context}")
    logger.error(f"║ 🔥 Тип ошибки: {type(error).__name__}")
    logger.error(f"║ 💥 Сообщение: {str(error)}")
    logger.error("╚═══════════════════════════════════════════════════════════", exc_info=True)
