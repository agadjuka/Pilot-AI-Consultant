"""Create services and masters tables

Revision ID: 001
Revises: 
Create Date: 2025-10-12 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Создаем таблицу services
    op.create_table('services',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('duration_minutes', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_services_id'), 'services', ['id'], unique=False)
    op.create_index(op.f('ix_services_name'), 'services', ['name'], unique=False)

    # Создаем таблицу masters
    op.create_table('masters',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('specialization', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_masters_id'), 'masters', ['id'], unique=False)
    op.create_index(op.f('ix_masters_name'), 'masters', ['name'], unique=False)

    # Создаем ассоциативную таблицу master_services
    op.create_table('master_services',
        sa.Column('master_id', sa.Integer(), nullable=False),
        sa.Column('service_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['master_id'], ['masters.id'], ),
        sa.ForeignKeyConstraint(['service_id'], ['services.id'], ),
        sa.PrimaryKeyConstraint('master_id', 'service_id')
    )


def downgrade() -> None:
    # Удаляем таблицы в обратном порядке
    op.drop_table('master_services')
    op.drop_index(op.f('ix_masters_name'), table_name='masters')
    op.drop_index(op.f('ix_masters_id'), table_name='masters')
    op.drop_table('masters')
    op.drop_index(op.f('ix_services_name'), table_name='services')
    op.drop_index(op.f('ix_services_id'), table_name='services')
    op.drop_table('services')

