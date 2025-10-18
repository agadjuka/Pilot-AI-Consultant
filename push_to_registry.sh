#!/bin/bash

# Скрипт для отправки Docker образа в Yandex Container Registry
# Использование: ./push_to_registry.sh

set -e  # Остановить выполнение при ошибке

# Конфигурация
REGISTRY="cr.yandex/crpjmbnc945su0h9f23k"
IMAGE_NAME="beauty-salon-ai"
TAG="latest"
FULL_IMAGE_NAME="${REGISTRY}/${IMAGE_NAME}:${TAG}"

echo "🚀 Начинаем отправку Docker образа в Yandex Container Registry..."
echo "📦 Образ: ${FULL_IMAGE_NAME}"

# Проверяем, что Docker запущен
if ! docker info > /dev/null 2>&1; then
    echo "❌ Ошибка: Docker не запущен или недоступен"
    exit 1
fi

# Проверяем, что образ существует локально
if ! docker image inspect "${FULL_IMAGE_NAME}" > /dev/null 2>&1; then
    echo "❌ Ошибка: Образ ${FULL_IMAGE_NAME} не найден локально"
    echo "💡 Сначала выполните: docker build -t ${FULL_IMAGE_NAME} ."
    exit 1
fi

echo "✅ Образ найден локально"

# Выполняем push
echo "📤 Отправляем образ в реестр..."
if docker push "${FULL_IMAGE_NAME}"; then
    echo "✅ Образ успешно отправлен в Yandex Container Registry!"
    echo "🔗 Образ доступен по адресу: ${FULL_IMAGE_NAME}"
else
    echo "❌ Ошибка при отправке образа"
    exit 1
fi

echo "🎉 Готово!"


