#!/bin/bash

# Скрипт для быстрого просмотра логов
echo "📊 Получаем последние логи..."

# Получаем последние 50 логов
yc logging read --group-id e2353vds180sba50n9df --limit 50

echo ""
echo "🔍 Для получения большего количества логов используйте:"
echo "   yc logging read --group-id e2353vds180sba50n9df --limit 100"
echo ""
echo "📅 Для логов за определенный период используйте:"
echo "   yc logging read --group-id e2353vds180sba50n9df --since 2025-10-18T10:00:00Z --limit 100"
