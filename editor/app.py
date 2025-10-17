"""
Flask-приложение для редактирования конфигурационных файлов AI-бота.
Предоставляет API для работы с dialogue_patterns.json и prompt_builder_service.py.
"""

import os
import json
import re
import shutil
from flask import Flask, request, jsonify, render_template

# Создаем экземпляр Flask-приложения
app = Flask(__name__)

# Пути к целевым файлам (относительно корня проекта)
PATTERNS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'dialogue_patterns.json')
PROMPTS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'app', 'services', 'prompt_builder_service.py')


def create_backup(file_path: str) -> str:
    """
    Создает резервную копию файла.
    
    Args:
        file_path: Путь к файлу для резервного копирования
        
    Returns:
        Путь к созданной резервной копии
    """
    backup_path = file_path + '.bak'
    shutil.copy(file_path, backup_path)
    return backup_path


def extract_template_content(content: str, template_name: str) -> str:
    """
    Извлекает содержимое шаблона из Python-файла с помощью регулярных выражений.
    
    Args:
        content: Содержимое файла
        template_name: Имя переменной шаблона
        
    Returns:
        Содержимое шаблона
    """
    # Паттерн для поиска переменной с тройными кавычками
    pattern = rf'{template_name}\s*=\s*"""([\s\S]*?)"""'
    match = re.search(pattern, content)
    
    if match:
        return match.group(1).strip()
    else:
        return ""


def replace_template_content(content: str, template_name: str, new_content: str) -> str:
    """
    Заменяет содержимое шаблона в Python-файле.
    
    Args:
        content: Содержимое файла
        template_name: Имя переменной шаблона
        new_content: Новое содержимое шаблона
        
    Returns:
        Обновленное содержимое файла
    """
    # Паттерн для замены содержимого между тройными кавычками
    pattern = rf'({template_name}\s*=\s*""")[\s\S]*?(""")'
    replacement = rf'\1{new_content}\2'
    
    return re.sub(pattern, replacement, content)


# === API ДЛЯ РАБОТЫ С DIALOGUE_PATTERNS.JSON ===

@app.route('/api/patterns', methods=['GET'])
def get_patterns():
    """
    Получает содержимое dialogue_patterns.json.
    
    Returns:
        JSON с паттернами диалогов
    """
    try:
        with open(PATTERNS_FILE, 'r', encoding='utf-8') as f:
            patterns = json.load(f)
        return jsonify(patterns)
    except FileNotFoundError:
        return jsonify({'error': 'Файл dialogue_patterns.json не найден'}), 404
    except json.JSONDecodeError as e:
        return jsonify({'error': f'Ошибка парсинга JSON: {str(e)}'}), 400
    except Exception as e:
        return jsonify({'error': f'Ошибка чтения файла: {str(e)}'}), 500


@app.route('/api/patterns', methods=['POST'])
def save_patterns():
    """
    Сохраняет обновленные паттерны в dialogue_patterns.json.
    
    Returns:
        JSON с результатом операции
    """
    try:
        # Получаем данные из запроса
        patterns_data = request.get_json()
        
        if not patterns_data:
            return jsonify({'error': 'Отсутствуют данные для сохранения'}), 400
        
        # Создаем резервную копию
        backup_path = create_backup(PATTERNS_FILE)
        
        # Сохраняем обновленные данные с красивым форматированием
        with open(PATTERNS_FILE, 'w', encoding='utf-8') as f:
            json.dump(patterns_data, f, indent=2, ensure_ascii=False)
        
        return jsonify({
            'success': True,
            'message': 'Паттерны успешно сохранены',
            'backup': backup_path
        })
        
    except Exception as e:
        return jsonify({'error': f'Ошибка сохранения: {str(e)}'}), 500


# === API ДЛЯ РАБОТЫ С PROMPT_BUILDER_SERVICE.PY ===

@app.route('/api/prompts', methods=['GET'])
def get_prompts():
    """
    Получает содержимое шаблонов из prompt_builder_service.py.
    
    Returns:
        JSON с содержимым трех шаблонов
    """
    try:
        with open(PROMPTS_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Извлекаем содержимое трех шаблонов
        classification = extract_template_content(content, 'CLASSIFICATION_TEMPLATE')
        thinking = extract_template_content(content, 'THINKING_TEMPLATE')
        synthesis = extract_template_content(content, 'SYNTHESIS_TEMPLATE')
        
        return jsonify({
            'classification': classification,
            'thinking': thinking,
            'synthesis': synthesis
        })
        
    except FileNotFoundError:
        return jsonify({'error': 'Файл prompt_builder_service.py не найден'}), 404
    except Exception as e:
        return jsonify({'error': f'Ошибка чтения файла: {str(e)}'}), 500


@app.route('/api/prompts', methods=['POST'])
def save_prompts():
    """
    Сохраняет обновленные шаблоны в prompt_builder_service.py.
    
    Returns:
        JSON с результатом операции
    """
    try:
        # Получаем данные из запроса
        prompts_data = request.get_json()
        
        if not prompts_data:
            return jsonify({'error': 'Отсутствуют данные для сохранения'}), 400
        
        # Проверяем наличие всех необходимых ключей
        required_keys = ['classification', 'thinking', 'synthesis']
        for key in required_keys:
            if key not in prompts_data:
                return jsonify({'error': f'Отсутствует обязательное поле: {key}'}), 400
        
        # Создаем резервную копию
        backup_path = create_backup(PROMPTS_FILE)
        
        # Читаем текущее содержимое файла
        with open(PROMPTS_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Заменяем содержимое каждого шаблона
        content = replace_template_content(content, 'CLASSIFICATION_TEMPLATE', prompts_data['classification'])
        content = replace_template_content(content, 'THINKING_TEMPLATE', prompts_data['thinking'])
        content = replace_template_content(content, 'SYNTHESIS_TEMPLATE', prompts_data['synthesis'])
        
        # Сохраняем обновленное содержимое
        with open(PROMPTS_FILE, 'w', encoding='utf-8') as f:
            f.write(content)
        
        return jsonify({
            'success': True,
            'message': 'Шаблоны успешно сохранены',
            'backup': backup_path
        })
        
    except Exception as e:
        return jsonify({'error': f'Ошибка сохранения: {str(e)}'}), 500


# === ОСНОВНОЙ МАРШРУТ ===

@app.route('/')
def index():
    """
    Основная страница редактора.
    
    Returns:
        HTML-шаблон главной страницы
    """
    return render_template('index.html')


# === ТОЧКА ВХОДА ДЛЯ ЗАПУСКА ===

if __name__ == '__main__':
    app.run(debug=True, port=5000)
