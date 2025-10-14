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
            
            # Проверяем, что стадия имеет либо полную структуру (principles + examples), 
            # либо только описание (для специальных стадий типа conflict_escalation)
            has_principles = 'principles' in stage_data
            has_examples = 'examples' in stage_data
            has_description = 'description' in stage_data
            
            if has_principles or has_examples:
                # Обычная стадия - должна иметь оба поля
                if not has_principles:
                    raise ValueError(f"Стадия '{stage_id}' содержит 'examples', но не содержит 'principles'")
                if not has_examples:
                    raise ValueError(f"Стадия '{stage_id}' содержит 'principles', но не содержит 'examples'")
            elif has_description:
                # Специальная стадия только с описанием - это нормально
                pass
            else:
                # Стадия должна иметь либо полную структуру, либо описание
                raise ValueError(f"Стадия '{stage_id}' должна содержать либо 'principles' и 'examples', либо 'description'")
        
        return patterns
        
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(f"Ошибка парсинга JSON файла паттернов: {e}")


# Глобальный экземпляр паттернов
dialogue_patterns = load_patterns()
