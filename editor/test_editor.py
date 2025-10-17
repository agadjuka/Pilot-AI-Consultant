#!/usr/bin/env python3
"""
Тестовый скрипт для проверки работы редактора персоны.
Проверяет корректность обработки списков в многострочных полях.
"""

import requests
import json
import time

# URL редактора
BASE_URL = "http://localhost:5000"

def test_get_patterns():
    """Тест получения паттернов"""
    print("🔍 Тестируем GET /api/patterns...")
    
    try:
        response = requests.get(f"{BASE_URL}/api/patterns")
        if response.status_code == 200:
            data = response.json()
            print("✅ GET запрос успешен")
            
            # Проверяем структуру данных
            for stage_name, stage_data in data.items():
                if isinstance(stage_data, dict):
                    # Проверяем, что поля преобразованы в строки для отображения
                    if 'thinking_scenario' in stage_data:
                        if isinstance(stage_data['thinking_scenario'], str):
                            print(f"✅ {stage_name}.thinking_scenario - строка (для textarea)")
                        else:
                            print(f"❌ {stage_name}.thinking_scenario - не строка: {type(stage_data['thinking_scenario'])}")
                    
                    if 'synthesis_scenario' in stage_data:
                        if isinstance(stage_data['synthesis_scenario'], str):
                            print(f"✅ {stage_name}.synthesis_scenario - строка (для textarea)")
                        else:
                            print(f"❌ {stage_name}.synthesis_scenario - не строка: {type(stage_data['synthesis_scenario'])}")
            
            return data
        else:
            print(f"❌ GET запрос неуспешен: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Ошибка GET запроса: {e}")
        return None

def test_save_patterns(original_data):
    """Тест сохранения паттернов"""
    print("\n💾 Тестируем POST /api/patterns...")
    
    if not original_data:
        print("❌ Нет исходных данных для тестирования")
        return False
    
    # Создаем тестовые данные с многострочными полями
    test_data = original_data.copy()
    
    # Находим первую стадию для тестирования
    first_stage = list(test_data.keys())[0]
    stage_data = test_data[first_stage]
    
    # Добавляем тестовые многострочные данные
    stage_data['thinking_scenario'] = [
        "1. Первая строка тестового сценария",
        "2. Вторая строка тестового сценария", 
        "3. Третья строка тестового сценария"
    ]
    stage_data['synthesis_scenario'] = [
        "1. Первая строка синтеза",
        "2. Вторая строка синтеза"
    ]
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/patterns",
            headers={'Content-Type': 'application/json'},
            json=test_data
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                print("✅ POST запрос успешен")
                return True
            else:
                print(f"❌ POST запрос неуспешен: {result}")
                return False
        else:
            print(f"❌ POST запрос неуспешен: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Ошибка POST запроса: {e}")
        return False

def test_roundtrip():
    """Тест полного цикла: получение -> изменение -> сохранение -> получение"""
    print("\n🔄 Тестируем полный цикл обработки...")
    
    # 1. Получаем данные
    original_data = test_get_patterns()
    if not original_data:
        return False
    
    # 2. Сохраняем тестовые данные
    if not test_save_patterns(original_data):
        return False
    
    # 3. Получаем данные снова и проверяем
    print("\n🔍 Проверяем сохраненные данные...")
    updated_data = test_get_patterns()
    if not updated_data:
        return False
    
    # Проверяем, что данные сохранились корректно
    first_stage = list(updated_data.keys())[0]
    stage_data = updated_data[first_stage]
    
    thinking_scenario = stage_data.get('thinking_scenario', '')
    synthesis_scenario = stage_data.get('synthesis_scenario', '')
    
    if 'Первая строка тестового сценария' in thinking_scenario:
        print("✅ Тестовые данные thinking_scenario сохранились корректно")
    else:
        print("❌ Тестовые данные thinking_scenario не сохранились")
        return False
    
    if 'Первая строка синтеза' in synthesis_scenario:
        print("✅ Тестовые данные synthesis_scenario сохранились корректно")
    else:
        print("❌ Тестовые данные synthesis_scenario не сохранились")
        return False
    
    return True

def main():
    """Основная функция тестирования"""
    print("🚀 Запуск тестирования редактора персоны")
    print("=" * 50)
    
    # Ждем запуска сервера
    print("⏳ Ожидаем запуска сервера...")
    time.sleep(2)
    
    # Проверяем доступность сервера
    try:
        response = requests.get(f"{BASE_URL}/")
        if response.status_code != 200:
            print("❌ Сервер недоступен")
            return
    except:
        print("❌ Сервер недоступен")
        return
    
    print("✅ Сервер доступен")
    
    # Запускаем тесты
    success = test_roundtrip()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 Все тесты прошли успешно!")
        print("✅ Редактор корректно обрабатывает многострочные поля")
    else:
        print("❌ Тесты не прошли")
    
    return success

if __name__ == "__main__":
    main()
