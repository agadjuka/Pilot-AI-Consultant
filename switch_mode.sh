#!/bin/bash

# Скрипт для переключения между обычным режимом и режимом заглушки
# Используется для тестирования webhook'ов без базы данных

echo "🔄 Переключение режима работы приложения..."

if [ "$1" = "stub" ]; then
    echo "🔧 Включаем режим заглушки (без БД)..."
    
    # Создаем резервные копии оригинальных файлов
    cp app/main.py app/main_original.py.bak
    cp app/api/telegram.py app/api/telegram_original.py.bak
    
    # Заменяем на версии с заглушками
    cp app/main_stub.py app/main.py
    cp app/api/telegram_stub.py app/api/telegram.py
    
    echo "✅ Режим заглушки включен!"
    echo "📊 Webhook'и будут работать без базы данных"
    echo "🎯 Сообщения будут обрабатываться заглушками"
    
elif [ "$1" = "normal" ]; then
    echo "🔧 Включаем обычный режим (с БД)..."
    
    # Восстанавливаем оригинальные файлы
    if [ -f "app/main_original.py.bak" ]; then
        cp app/main_original.py.bak app/main.py
        echo "✅ main.py восстановлен"
    else
        echo "❌ Резервная копия main.py не найдена"
    fi
    
    if [ -f "app/api/telegram_original.py.bak" ]; then
        cp app/api/telegram_original.py.bak app/api/telegram.py
        echo "✅ telegram.py восстановлен"
    else
        echo "❌ Резервная копия telegram.py не найдена"
    fi
    
    echo "✅ Обычный режим включен!"
    echo "📊 Webhook'и будут работать с базой данных"
    echo "🎯 Сообщения будут обрабатываться полноценно"
    
elif [ "$1" = "status" ]; then
    echo "📊 Проверка текущего режима..."
    
    if grep -q "STUB" app/main.py; then
        echo "🔧 Текущий режим: ЗАГЛУШКА (без БД)"
    else
        echo "🔧 Текущий режим: ОБЫЧНЫЙ (с БД)"
    fi
    
else
    echo "❌ Неверный параметр!"
    echo ""
    echo "Использование:"
    echo "  $0 stub    - включить режим заглушки (без БД)"
    echo "  $0 normal  - включить обычный режим (с БД)"
    echo "  $0 status  - проверить текущий режим"
    echo ""
    echo "Примеры:"
    echo "  ./switch_mode.sh stub"
    echo "  ./switch_mode.sh normal"
    echo "  ./switch_mode.sh status"
fi
