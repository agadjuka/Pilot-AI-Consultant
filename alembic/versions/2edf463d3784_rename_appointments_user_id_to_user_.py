"""rename appointments.user_id to user_telegram_id

Revision ID: 2edf463d3784
Revises: 723b38235632
Create Date: 2025-10-14 17:41:53.064133

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2edf463d3784'
down_revision: Union[str, None] = '723b38235632'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    exec_sql = conn.exec_driver_sql

    # Отключаем внешние ключи
    exec_sql("PRAGMA foreign_keys=off;")

    # Создаем новую таблицу с нужной схемой, если нет
    exec_sql(
        """
        CREATE TABLE IF NOT EXISTS appointments_new (
            id INTEGER NOT NULL PRIMARY KEY,
            user_telegram_id BIGINT NOT NULL,
            google_event_id VARCHAR NOT NULL UNIQUE,
            master_id INTEGER NOT NULL,
            service_id INTEGER NOT NULL,
            start_time DATETIME NOT NULL,
            end_time DATETIME NOT NULL,
            FOREIGN KEY(master_id) REFERENCES masters (id),
            FOREIGN KEY(service_id) REFERENCES services (id)
        );
        """
    )

    # Копируем данные, поддерживая как старый, так и новый столбец
    # Если user_telegram_id уже есть, используем его; иначе берем user_id
    # Попытка скопировать с учетом наличия колонок
    # 1) Проверим, есть ли колонка user_telegram_id
    has_user_tg = conn.exec_driver_sql(
        "PRAGMA table_info(appointments);").fetchall()
    col_names = {row[1] for row in has_user_tg}
    if "user_telegram_id" in col_names:
        exec_sql(
            """
            INSERT INTO appointments_new (id, user_telegram_id, google_event_id, master_id, service_id, start_time, end_time)
            SELECT id, user_telegram_id, google_event_id, master_id, service_id, start_time, end_time FROM appointments;
            """
        )
    else:
        exec_sql(
            """
            INSERT INTO appointments_new (id, user_telegram_id, google_event_id, master_id, service_id, start_time, end_time)
            SELECT id, user_id, google_event_id, master_id, service_id, start_time, end_time FROM appointments;
            """
        )

    # Заменяем таблицу
    exec_sql("DROP TABLE appointments;")
    exec_sql("ALTER TABLE appointments_new RENAME TO appointments;")

    # Индексы
    exec_sql("CREATE INDEX IF NOT EXISTS idx_user_time ON appointments (user_telegram_id, start_time);")
    exec_sql("CREATE INDEX IF NOT EXISTS ix_appointments_user_telegram_id ON appointments (user_telegram_id);")
    exec_sql("CREATE INDEX IF NOT EXISTS ix_appointments_id ON appointments (id);")

    # Включаем внешние ключи обратно
    exec_sql("PRAGMA foreign_keys=on;")


def downgrade() -> None:
    conn = op.get_bind()
    exec_sql = conn.exec_driver_sql

    exec_sql("PRAGMA foreign_keys=off;")

    exec_sql(
        """
        CREATE TABLE IF NOT EXISTS appointments_old (
            id INTEGER NOT NULL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            google_event_id VARCHAR NOT NULL UNIQUE,
            master_id INTEGER NOT NULL,
            service_id INTEGER NOT NULL,
            start_time DATETIME NOT NULL,
            end_time DATETIME NOT NULL,
            FOREIGN KEY(master_id) REFERENCES masters (id),
            FOREIGN KEY(service_id) REFERENCES services (id)
        );
        """
    )

    exec_sql(
        """
        INSERT INTO appointments_old (id, user_id, google_event_id, master_id, service_id, start_time, end_time)
        SELECT id, user_telegram_id, google_event_id, master_id, service_id, start_time, end_time FROM appointments;
        """
    )

    exec_sql("DROP TABLE appointments;")
    exec_sql("ALTER TABLE appointments_old RENAME TO appointments;")

    exec_sql("CREATE INDEX IF NOT EXISTS idx_user_time ON appointments (user_id, start_time);")
    exec_sql("CREATE INDEX IF NOT EXISTS ix_appointments_user_id ON appointments (user_id);")
    exec_sql("CREATE INDEX IF NOT EXISTS ix_appointments_id ON appointments (id);")

    exec_sql("PRAGMA foreign_keys=on;")

