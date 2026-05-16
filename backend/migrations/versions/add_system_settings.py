"""Add system_settings table for dynamic configuration
Revision ID: add_settings_2026
Revises: add_status_final
Create Date: 2026-05-17
"""
from alembic import op
import sqlalchemy as sa

revision = 'add_settings_2026'
down_revision = 'add_status_final'


def upgrade() -> None:
    op.create_table(
        'system_settings',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('key', sa.String(64), unique=True, nullable=False, index=True),
        sa.Column('value_type', sa.String(16), nullable=False),
        sa.Column('value_str', sa.Text(), nullable=True),
        sa.Column('updated_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), onupdate=sa.text('now()')),
        sa.Column('change_reason', sa.Text(), nullable=True),
    )
    op.create_index('ix_settings_key', 'system_settings', ['key'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_settings_key', table_name='system_settings')
    op.drop_table('system_settings')