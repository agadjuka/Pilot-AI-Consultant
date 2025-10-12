"""Create dialog_history table

Revision ID: 002
Revises: 001
Create Date: 2025-10-12 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Создаем таблицу dialog_history
    op.create_table('dialog_history',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('role', sa.String(length=10), nullable=False),
        sa.Column('message_text', sa.Text(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_dialog_history_id'), 'dialog_history', ['id'], unique=False)
    op.create_index(op.f('ix_dialog_history_user_id'), 'dialog_history', ['user_id'], unique=False)
    op.create_index(op.f('ix_dialog_history_timestamp'), 'dialog_history', ['timestamp'], unique=False)


def downgrade() -> None:
    # Удаляем таблицу dialog_history
    op.drop_index(op.f('ix_dialog_history_timestamp'), table_name='dialog_history')
    op.drop_index(op.f('ix_dialog_history_user_id'), table_name='dialog_history')
    op.drop_index(op.f('ix_dialog_history_id'), table_name='dialog_history')
    op.drop_table('dialog_history')

