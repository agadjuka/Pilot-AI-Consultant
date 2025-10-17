"""
Загрузчик паттернов диалогов из JSON файла.
Обеспечивает единоразовую загрузку паттернов при старте приложения.
"""

import json
import os
from typing import Dict, Any


def load_patterns() -> Dict[str, Any]:
    """
    Загружает паттерны диалогов из dialogue_patterns.json.
    
    Returns:
        Dict[str, Any]: Словарь с паттернами диалогов
        
    Raises:
        FileNotFoundError: Если файл dialogue_patterns.json не найден
        json.JSONDecodeError: Если файл содержит некорректный JSON
    """
    # Определяем путь к файлу относительно корня проекта
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(current_dir))
    patterns_file = os.path.join(project_root, "dialogue_patterns.json")
    
    if not os.path.exists(patterns_file):
        raise FileNotFoundError(f"Файл паттернов не найден: {patterns_file}")
    
    try:
        with open(patterns_file, 'r', encoding='utf-8') as f:
            patterns = json.load(f)
        
        # Валидация структуры
        if not isinstance(patterns, dict):
            raise ValueError("Файл паттернов должен содержать словарь")
        
        # Проверяем структуру стадий
        for stage_id, stage_data in patterns.items():
            if not isinstance(stage_data, dict):
                raise ValueError(f"Стадия '{stage_id}' должна быть словарем")
            
            # Проверяем новую структуру: goal обязательное, available_tools необязательное
            required_fields = ['goal']
            for field in required_fields:
                if field not in stage_data:
                    raise ValueError(f"Стадия '{stage_id}' должна содержать поле '{field}'")
            
            # Проверяем типы полей
            if not isinstance(stage_data['goal'], str):
                raise ValueError(f"Поле 'goal' в стадии '{stage_id}' должно быть строкой")
            
            # Проверяем тип available_tools только если поле присутствует
            if 'available_tools' in stage_data:
                if not isinstance(stage_data['available_tools'], list):
                    raise ValueError(f"Поле 'available_tools' в стадии '{stage_id}' должно быть списком")
            
            # Проверяем наличие хотя бы одного сценария (thinking_scenario или synthesis_scenario)
            has_thinking_scenario = 'thinking_scenario' in stage_data
            has_synthesis_scenario = 'synthesis_scenario' in stage_data
            
            if not has_thinking_scenario and not has_synthesis_scenario:
                raise ValueError(f"Стадия '{stage_id}' должна содержать хотя бы один сценарий: 'thinking_scenario' или 'synthesis_scenario'")
            
            # Проверяем thinking_scenario если есть
            if has_thinking_scenario:
                if not isinstance(stage_data['thinking_scenario'], list):
                    raise ValueError(f"Поле 'thinking_scenario' в стадии '{stage_id}' должно быть списком")
                for i, step in enumerate(stage_data['thinking_scenario']):
                    if not isinstance(step, str):
                        raise ValueError(f"Элемент {i} в 'thinking_scenario' стадии '{stage_id}' должен быть строкой")
            
            # Проверяем synthesis_scenario если есть
            if has_synthesis_scenario:
                if not isinstance(stage_data['synthesis_scenario'], list):
                    raise ValueError(f"Поле 'synthesis_scenario' в стадии '{stage_id}' должно быть списком")
                for i, step in enumerate(stage_data['synthesis_scenario']):
                    if not isinstance(step, str):
                        raise ValueError(f"Элемент {i} в 'synthesis_scenario' стадии '{stage_id}' должен быть строкой")
            
            # Проверяем, что все элементы available_tools - строки (только если поле присутствует)
            if 'available_tools' in stage_data:
                for i, tool in enumerate(stage_data['available_tools']):
                    if not isinstance(tool, str):
                        raise ValueError(f"Элемент {i} в 'available_tools' стадии '{stage_id}' должен быть строкой")
        
        return patterns
        
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(f"Ошибка парсинга JSON файла паттернов: {e}")


# Глобальный экземпляр паттернов
dialogue_patterns = load_patterns()
