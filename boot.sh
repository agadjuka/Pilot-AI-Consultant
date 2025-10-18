#!/bin/sh

# Печатаем переменные окружения для отладки
echo ">>> boot.sh: Переменные окружения:"
printenv
echo "--------------------------------"

# Запускаем наше Python-приложение
echo ">>> boot.sh: Запуск launch.py..."
python launch.py
