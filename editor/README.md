# Редактор конфигурации AI-бота

Простое Flask-приложение для визуального редактирования конфигурационных файлов AI-бота салона красоты.

## Структура проекта

```
editor/
├── app.py              # Основное Flask-приложение
├── run_editor.py       # Скрипт для запуска сервера
├── test_api.py         # Тестовый скрипт для проверки API
├── templates/
│   └── index.html      # HTML-шаблон главной страницы
└── static/             # Статические файлы (CSS/JS)
```

## Возможности

### API для работы с dialogue_patterns.json

- **GET `/api/patterns`** - Получение всех паттернов диалогов
- **POST `/api/patterns`** - Сохранение обновленных паттернов

### API для работы с prompt_builder_service.py

- **GET `/api/prompts`** - Получение содержимого трех шаблонов:
  - `CLASSIFICATION_TEMPLATE`
  - `THINKING_TEMPLATE` 
  - `SYNTHESIS_TEMPLATE`
- **POST `/api/prompts`** - Сохранение обновленных шаблонов

## Запуск

### Способ 1: Прямой запуск
```bash
cd editor
python app.py
```

### Способ 2: Через скрипт запуска
```bash
cd editor
python run_editor.py
```

Сервер будет доступен по адресу: http://localhost:5000

## Тестирование API

```bash
cd editor
python test_api.py
```

## Безопасность

- Перед каждой операцией записи создается резервная копия файла (`.bak`)
- Используются регулярные выражения для безопасного редактирования Python-файлов
- Валидация входных данных

## Примеры использования

### Получение паттернов диалогов
```bash
curl http://localhost:5000/api/patterns
```

### Получение шаблонов промптов
```bash
curl http://localhost:5000/api/prompts
```

### Сохранение обновленных паттернов
```bash
curl -X POST http://localhost:5000/api/patterns \
  -H "Content-Type: application/json" \
  -d '{"greeting": {"goal": "Новая цель"}}'
```

### Сохранение обновленных шаблонов
```bash
curl -X POST http://localhost:5000/api/prompts \
  -H "Content-Type: application/json" \
  -d '{"classification": "Новый шаблон", "thinking": "...", "synthesis": "..."}'
```
