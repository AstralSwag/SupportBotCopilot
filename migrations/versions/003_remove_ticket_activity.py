"""Remove ticket activity

Revision ID: 003
Revises: 002
Create Date: 2024-06-16 02:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Удаляем поле updated_at, так как оно использовалось для отслеживания активности
    op.drop_column('tickets', 'updated_at')


def downgrade() -> None:
    # Восстанавливаем поле updated_at
    op.add_column('tickets', sa.Column('updated_at', sa.DateTime(), nullable=True)) 