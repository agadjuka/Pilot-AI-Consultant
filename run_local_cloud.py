#!/usr/bin/env python3
"""
Скрипт для запуска веб-сервера в режиме "Локальное Облако".

Этот скрипт устанавливает переменную окружения ENV_FILE для использования
отдельной конфигурации (.env.local_cloud) и запускает сервер с настройками,
симулирующими облачную среду.
"""

import os

if __name__ == "__main__":
    # Устанавливаем переменную окружения для использования .env.local_cloud
    os.environ["ENV_FILE"] = ".env.local_cloud"
    
    import uvicorn
    from app.main import app
    
    print("🚀 Запуск сервера в режиме 'Локальное Облако'...")
    print("- Используется конфигурация из .env.local_cloud")
    print("- Сервер будет доступен на http://127.0.0.1:8080")
    print("- Для остановки нажмите Ctrl+C")
    print()
    
    uvicorn.run(app, host="127.0.0.1", port=8080)
