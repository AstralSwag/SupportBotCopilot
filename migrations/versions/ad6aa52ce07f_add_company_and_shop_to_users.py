"""add_company_and_shop_to_users

Revision ID: ad6aa52ce07f
Revises: 003
Create Date: 2025-06-17 13:30:46.723421

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ad6aa52ce07f'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('company', sa.String(), nullable=False, server_default=''))
    op.add_column('users', sa.Column('shop', sa.String(), nullable=False, server_default=''))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'shop')
    op.drop_column('users', 'company')
