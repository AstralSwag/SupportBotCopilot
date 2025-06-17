"""add_description_to_tickets

Revision ID: 24a7d3ccb336
Revises: ad6aa52ce07f
Create Date: 2024-06-17 16:34:32.123456

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '24a7d3ccb336'
down_revision: Union[str, None] = 'ad6aa52ce07f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Добавляем поле description
    op.add_column('tickets', sa.Column('description', sa.Text(), nullable=False, server_default=''))
    
    # Делаем поля plane_ticket_id и mattermost_post_id необязательными
    op.alter_column('tickets', 'plane_ticket_id',
               existing_type=sa.String(),
               nullable=True)
    op.alter_column('tickets', 'mattermost_post_id',
               existing_type=sa.String(),
               nullable=True)
    
    # Добавляем поле closed_at
    op.add_column('tickets', sa.Column('closed_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    # Удаляем поле closed_at
    op.drop_column('tickets', 'closed_at')
    
    # Возвращаем поля plane_ticket_id и mattermost_post_id как обязательные
    op.alter_column('tickets', 'mattermost_post_id',
               existing_type=sa.String(),
               nullable=False)
    op.alter_column('tickets', 'plane_ticket_id',
               existing_type=sa.String(),
               nullable=False)
    
    # Удаляем поле description
    op.drop_column('tickets', 'description')
