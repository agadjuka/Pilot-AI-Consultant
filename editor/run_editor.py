"""
Скрипт для запуска Flask-сервера редактора конфигурации.
"""

import os
import sys

# Добавляем текущую директорию в путь для импорта
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app

if __name__ == '__main__':
    print("Запуск редактора конфигурации AI-бота...")
    print("Сервер будет доступен по адресу: http://localhost:5000")
    print("Для остановки нажмите Ctrl+C")
    print("-" * 50)
    
    app.run(debug=True, port=5000, host='127.0.0.1')
