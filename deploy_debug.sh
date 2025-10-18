#!/bin/bash

# Скрипт для быстрого деплоя с отладочным логированием
echo "🚀 Начинаем деплой с отладочным логированием..."

# Сборка образа
echo "📦 Собираем Docker образ..."
docker build -t beauty-salon-ai-debug .

# Тегирование для Yandex Container Registry
echo "🏷️ Тегируем образ для Yandex Cloud..."
docker tag beauty-salon-ai-debug cr.yandex/crplkqet5mvgd0a181mo/beauty-salon-ai:debug-$(date +%Y%m%d-%H%M%S)
docker tag beauty-salon-ai-debug cr.yandex/crplkqet5mvgd0a181mo/beauty-salon-ai:latest

# Аутентификация в Yandex Container Registry
echo "🔐 Аутентификация в Yandex Container Registry..."
yc container registry configure-docker

# Загрузка образа
echo "📤 Загружаем образ в Yandex Container Registry..."
docker push cr.yandex/crplkqet5mvgd0a181mo/beauty-salon-ai:latest

echo "✅ Деплой завершен!"
echo "📊 Для просмотра логов используйте:"
echo "   yc logging read --group-id e2353vds180sba50n9df --limit 100"
