"""Add ticket title

Revision ID: 002
Revises: 001
Create Date: 2024-03-21

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None

def upgrade():
    # Добавляем колонку title в таблицу tickets
    op.add_column('tickets', sa.Column('title', sa.String(100), nullable=True))
    
    # Заполняем существующие записи значением по умолчанию
    op.execute("UPDATE tickets SET title = 'Обращение' WHERE title IS NULL")
    
    # Делаем колонку NOT NULL
    op.alter_column('tickets', 'title',
               existing_type=sa.String(100),
               nullable=False)

def downgrade():
    # Удаляем колонку title из таблицы tickets
    op.drop_column('tickets', 'title') 