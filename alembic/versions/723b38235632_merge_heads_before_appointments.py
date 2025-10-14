"""merge heads before appointments

Revision ID: 723b38235632
Revises: 003_create_clients_table, 4148ed0c3e72
Create Date: 2025-10-14 17:41:07.062354

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '723b38235632'
down_revision: Union[str, None] = ('003_create_clients_table', '4148ed0c3e72')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

