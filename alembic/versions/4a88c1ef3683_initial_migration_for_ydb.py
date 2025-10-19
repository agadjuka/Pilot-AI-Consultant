"""Initial migration for YDB

Revision ID: 4a88c1ef3683
Revises: 
Create Date: 2025-10-19 09:22:37.054702

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4a88c1ef3683'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Создание таблицы services
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

    # Создание таблицы masters
    op.create_table('masters',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('specialization', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_masters_id'), 'masters', ['id'], unique=False)
    op.create_index(op.f('ix_masters_name'), 'masters', ['name'], unique=False)

    # Создание ассоциативной таблицы master_services
    op.create_table('master_services',
        sa.Column('master_id', sa.Integer(), nullable=False),
        sa.Column('service_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['master_id'], ['masters.id'], ),
        sa.ForeignKeyConstraint(['service_id'], ['services.id'], ),
        sa.PrimaryKeyConstraint('master_id', 'service_id')
    )

    # Создание таблицы clients
    op.create_table('clients',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('telegram_id', sa.Integer(), nullable=False),
        sa.Column('first_name', sa.String(length=255), nullable=True),
        sa.Column('phone_number', sa.String(length=32), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('telegram_id', name='uq_clients_telegram_id')
    )
    op.create_index(op.f('ix_clients_id'), 'clients', ['id'], unique=False)
    op.create_index(op.f('ix_clients_telegram_id'), 'clients', ['telegram_id'], unique=False)

    # Создание таблицы appointments
    op.create_table('appointments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_telegram_id', sa.BigInteger(), nullable=False),
        sa.Column('master_id', sa.Integer(), nullable=False),
        sa.Column('service_id', sa.Integer(), nullable=False),
        sa.Column('start_time', sa.DateTime(), nullable=False),
        sa.Column('end_time', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['master_id'], ['masters.id'], ),
        sa.ForeignKeyConstraint(['service_id'], ['services.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_appointments_id'), 'appointments', ['id'], unique=False)
    op.create_index(op.f('ix_appointments_user_telegram_id'), 'appointments', ['user_telegram_id'], unique=False)
    op.create_index('idx_user_time', 'appointments', ['user_telegram_id', 'start_time'], unique=False)

    # Создание таблицы dialog_history
    op.create_table('dialog_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.BigInteger(), nullable=False),
        sa.Column('role', sa.String(length=10), nullable=False),
        sa.Column('message_text', sa.Text(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_dialog_history_user_id'), 'dialog_history', ['user_id'], unique=False)
    op.create_index(op.f('ix_dialog_history_timestamp'), 'dialog_history', ['timestamp'], unique=False)


def downgrade() -> None:
    # Удаление таблиц в обратном порядке
    op.drop_index(op.f('ix_dialog_history_timestamp'), table_name='dialog_history')
    op.drop_index(op.f('ix_dialog_history_user_id'), table_name='dialog_history')
    op.drop_table('dialog_history')
    
    op.drop_index('idx_user_time', table_name='appointments')
    op.drop_index(op.f('ix_appointments_user_telegram_id'), table_name='appointments')
    op.drop_index(op.f('ix_appointments_id'), table_name='appointments')
    op.drop_table('appointments')
    
    op.drop_index(op.f('ix_clients_telegram_id'), table_name='clients')
    op.drop_index(op.f('ix_clients_id'), table_name='clients')
    op.drop_table('clients')
    
    op.drop_table('master_services')
    
    op.drop_index(op.f('ix_masters_name'), table_name='masters')
    op.drop_index(op.f('ix_masters_id'), table_name='masters')
    op.drop_table('masters')
    
    op.drop_index(op.f('ix_services_name'), table_name='services')
    op.drop_index(op.f('ix_services_id'), table_name='services')
    op.drop_table('services')

