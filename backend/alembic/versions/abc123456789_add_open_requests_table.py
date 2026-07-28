"""add open_requests table

Revision ID: abc123456789
Revises: 74722ade6207
Create Date: 2026-07-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'abc123456789'
down_revision: Union[str, None] = '45a54bec1cb4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create open_requests table
    op.create_table(
        'open_requests',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('client_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('budget', sa.DECIMAL(precision=10, scale=2), nullable=True),
        sa.Column('location_lat', sa.DECIMAL(precision=10, scale=8), nullable=True),
        sa.Column('location_lng', sa.DECIMAL(precision=11, scale=8), nullable=True),
        sa.Column(
            'status',
            sa.Enum('OPEN', 'ASSIGNED', 'CLOSED', 'CANCELLED', name='openrequeststatus'),
            nullable=True,
        ),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=True,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_open_requests_id'), 'open_requests', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_open_requests_id'), table_name='open_requests')
    op.drop_table('open_requests')
