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
RUN poetry config virtualenvs.in-project true && poetry install --only=main --no-interaction --no-ansi --no-root


# --- Этап 2: Создание финальнytого образа ---
# Используем тот же базовый образ для уменьшения размера
FROM python:3.10-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем созданное ранее виртуальное окружение из этапа сборки
COPY --from=builder /app/.venv .venv

# Активируем виртуальное окружение для последующих команд
ENV PATH="/app/.venv/bin:$PATH"

# Копируем исходный код приложения
COPY ./app ./app

# Команда для запуска приложения
# Uvicorn будет запущен на порту 8080, что является стандартом для Cloud Run
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080