from logging.config import fileConfig
from dotenv import load_dotenv
import os

# Загружаем переменные окружения из .env файла
load_dotenv()

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata

# Импортируем нашу базовую модель, чтобы Alembic "увидел" все наши таблицы
from app.core.database import Base
from app.models import * # Импортируем все модели

target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    # Используем те же настройки, что и основное приложение
    from app.core.config import settings
    import os
    
    # Формируем URL так же, как в основном приложении
    endpoint = settings.YDB_ENDPOINT
    database = settings.YDB_DATABASE
    # Убираем grpcs:// из endpoint для правильного парсинга
    endpoint_clean = endpoint.replace('grpcs://', '').replace('grpc://', '')
    url = f"ydb://{endpoint_clean}/{database}"
    
    context.configure(
        url=url,
        target_metadata=target_metadata,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    # Используем те же настройки, что и основное приложение
    from app.core.config import settings
    from sqlalchemy import create_engine
    import ydb
    import os
    
    # Формируем строку подключения так же, как в основном приложении
    endpoint = settings.YDB_ENDPOINT
    database = settings.YDB_DATABASE
    # Убираем grpcs:// из endpoint для правильного парсинга
    endpoint_clean = endpoint.replace('grpcs://', '').replace('grpc://', '')
    connection_string = f"ydb://{endpoint_clean}/{database}"
    
    # Получаем учетные данные из Service Account ключа
    service_account_key_file = os.getenv("YC_SERVICE_ACCOUNT_KEY_FILE", "key.json")
    
    # Проверяем существование файла ключа
    # Сначала проверяем относительный путь, затем в корне проекта
    key_file_path = service_account_key_file
    if not os.path.exists(key_file_path):
        # Пробуем найти файл в корне проекта (на уровень выше scripts/)
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        key_file_path = os.path.join(project_root, service_account_key_file)
    
    credentials = ydb.iam.ServiceAccountCredentials.from_file(key_file_path)
    
    connectable = create_engine(
        connection_string,
        connect_args={"credentials": credentials},
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


# Alembic будет вызывать эти функции только когда это необходимо
# Не выполняем миграции при загрузке модуля

# Регистрируем функции миграций для Alembic
# Alembic автоматически вызовет нужную функцию в зависимости от режима
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

