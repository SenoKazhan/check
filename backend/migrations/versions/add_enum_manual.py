"""Add measurement status enum and column

Revision ID: add_status_final
Revises: 953f31aa4b13
Create Date: 2026-05-14

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'add_status_final'
down_revision: Union[str, None] = '953f31aa4b13'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Создаём ENUM тип в PostgreSQL (с проверкой существования)
    measurement_status = postgresql.ENUM(
        'pending', 'processing', 'completed', 'failed', 'needs_review',
        name='measurement_status_enum',
        create_type=True
    )
    measurement_status.create(op.get_bind(), checkfirst=True)
    
    # 2. Добавляем колонку status в таблицу measurements
    op.add_column('measurements', 
        sa.Column('status', measurement_status, nullable=False, server_default='pending')
    )
    
    # 3. Создаём индекс для быстрого поиска по статусу
    op.create_index('ix_measurements_status', 'measurements', ['status'])


def downgrade() -> None:
    # 1. Удаляем индекс
    op.drop_index('ix_measurements_status', table_name='measurements')
    
    # 2. Удаляем колонку
    op.drop_column('measurements', 'status')
    
    # 3. Удаляем ENUM тип (с проверкой)
    measurement_status = postgresql.ENUM(
        'pending', 'processing', 'completed', 'failed', 'needs_review',
        name='measurement_status_enum',
        create_type=False
    )
    measurement_status.drop(op.get_bind(), checkfirst=True)