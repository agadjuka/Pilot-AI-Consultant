"""
Тестовый скрипт для проверки API редактора конфигурации.
"""

import requests
import json

def test_api():
    """Тестирует основные эндпоинты API."""
    base_url = "http://localhost:5000"
    
    print("=== Тестирование API редактора конфигурации ===\n")
    
    # Тест 1: Получение паттернов
    print("1. Тестирование GET /api/patterns...")
    try:
        response = requests.get(f"{base_url}/api/patterns")
        if response.status_code == 200:
            patterns = response.json()
            print(f"✓ Успешно получено {len(patterns)} паттернов")
            print(f"  Первый паттерн: {list(patterns.keys())[0]}")
        else:
            print(f"✗ Ошибка: {response.status_code} - {response.text}")
    except requests.exceptions.ConnectionError:
        print("✗ Не удается подключиться к серверу. Убедитесь, что Flask-приложение запущено.")
        return
    except Exception as e:
        print(f"✗ Ошибка: {e}")
        return
    
    # Тест 2: Получение промптов
    print("\n2. Тестирование GET /api/prompts...")
    try:
        response = requests.get(f"{base_url}/api/prompts")
        if response.status_code == 200:
            prompts = response.json()
            print("✓ Успешно получены шаблоны:")
            for key, value in prompts.items():
                print(f"  {key}: {len(value)} символов")
        else:
            print(f"✗ Ошибка: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"✗ Ошибка: {e}")
    
    # Тест 3: Главная страница
    print("\n3. Тестирование GET /...")
    try:
        response = requests.get(f"{base_url}/")
        if response.status_code == 200:
            print("✓ Главная страница доступна")
        else:
            print(f"✗ Ошибка: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"✗ Ошибка: {e}")
    
    print("\n=== Тестирование завершено ===")

if __name__ == "__main__":
    test_api()
