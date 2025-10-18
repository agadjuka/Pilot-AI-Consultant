import uvicorn
import traceback
import logging

# Настраиваем базовый логгер, чтобы видеть вывод в Yandex Cloud
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

logger.info(">>> launch.py: Скрипт запущен.")

try:
    # Эта строка может вызвать ошибку, если есть проблемы с импортами внутри app.main
    from app.main import app
    logger.info(">>> launch.py: 'app' из 'app.main' успешно импортирован.")
    
    # Если импорт прошел, запускаем uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="debug")

except Exception as e:
    # Если на этапе импорта или инициализации uvicorn произошла ошибка,
    # мы ее поймаем, запишем в лог и завершим процесс с ошибкой.
    logger.error("!!! КРИТИЧЕСКАЯ ОШИБКА ПРИ СТАРТЕ ПРИЛОЖЕНИЯ !!!")
    logger.error(traceback.format_exc()) # Печатаем полный traceback
    exit(1) # Завершаем с ненулевым кодом
