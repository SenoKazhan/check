
"""Add measurement status enum

Revision ID: xxxx
Revises: 953f31aa4b13
Create Date: 2026-05-14

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'xxxx'
down_revision = '953f31aa4b13'

def upgrade() -> None:
    # 1. Создаём ENUM-тип в PostgreSQL
    measurement_status = sa.Enum(
        'pending', 'processing', 'completed', 'failed', 'needs_review',
        name='measurement_status',
        create_type=True
    )
    measurement_status.create(op.get_bind(), checkfirst=True)
    
    # 2. Добавляем колонку status с дефолтным значением
    op.add_column(
        'measurements',
        sa.Column(
            'status',
            measurement_status,
            nullable=False,
            server_default='pending'
        )
    )
    
    # 3. Создаём индекс для фильтрации по статусу
    op.create_index('ix_measurements_status', 'measurements', ['status'])

def downgrade() -> None:
    op.drop_index('ix_measurements_status', table_name='measurements')
    op.drop_column('measurements', 'status')
    
    # Удаляем ENUM-тип (осторожно: если используется в других таблицах)
    sa.Enum(name='measurement_status').drop(op.get_bind(), checkfirst=True)