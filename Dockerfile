# --- Этап 1: Сборка зависимостей ---
# Используем официальный образ Python как базовый для сборки
FROM python:3.10-slim as builder

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем Poetry
RUN pip install poetry

# Копируем файлы управления зависимостями
COPY poetry.lock pyproject.toml ./

# Устанавливаем зависимости проекта, исключая dev-зависимости,
# и создаем виртуальное окружение внутри /app/.venv
RUN poetry config virtualenvs.create false && \
    poetry install --no-root --no-dev --no-interaction --no-ansi


# --- Этап 2: Создание финальнytого образа ---
# Используем тот же базовый образ для уменьшения размера
FROM python:3.10-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем установленные зависимости из этапа сборки
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Копируем исходный код приложения
COPY app ./app
COPY dialogue_patterns.json .
COPY scripts ./scripts

# Команда для запуска приложения
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]