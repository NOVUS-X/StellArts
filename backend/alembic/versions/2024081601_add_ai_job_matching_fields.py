"""add ai job matching fields

Revision ID: 2024081601
Revises: abc123456789
Create Date: 2024-08-16 01:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY

# revision identifiers, used by Alembic.
revision = '2024081601'
down_revision = 'abc123456789'
branch_labels = None
depends_on = None


def upgrade():
    # Add AI Job Matching fields to bookings table
    op.add_column(
        'bookings',
        sa.Column('specialty_tags', ARRAY(sa.String), nullable=True)
    )
    
    op.add_column(
        'bookings',
        sa.Column('matched_artisan_ids', ARRAY(sa.Integer), nullable=True)
    )
    
    # Add AI Price Estimation fields to bookings table
    op.add_column(
        'bookings',
        sa.Column('ai_estimate_min', sa.DECIMAL(10, 2), nullable=True)
    )
    op.add_column(
        'bookings',
        sa.Column('ai_estimate_max', sa.DECIMAL(10, 2), nullable=True)
    )
    op.add_column(
        'bookings',
        sa.Column('ai_estimate_confidence', sa.DECIMAL(3, 2), nullable=True)
    )
    op.add_column(
        'bookings',
        sa.Column('ai_estimate_method', sa.String(20), nullable=True)
    )
    
    # Create LLM request tracking table
    op.create_table(
        'llm_requests',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('request_id', sa.String(50), unique=True, nullable=False),
        sa.Column('provider', sa.String(20), nullable=False),
        sa.Column('operation', sa.String(50), nullable=False),
        sa.Column('input_length', sa.Integer, nullable=True),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('response_time_ms', sa.Integer, nullable=True),
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('retries', sa.Integer, default=0),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True)
    )
    
    # Create indexes for llm_requests table
    op.create_index('idx_llm_requests_provider_status', 'llm_requests', ['provider', 'status'])
    op.create_index('idx_llm_requests_created_at', 'llm_requests', ['created_at'])


def downgrade():
    # Drop indexes
    op.drop_index('idx_llm_requests_created_at', table_name='llm_requests')
    op.drop_index('idx_llm_requests_provider_status', table_name='llm_requests')
    
    # Drop llm_requests table
    op.drop_table('llm_requests')
    
    # Remove AI fields from bookings table
    op.drop_column('bookings', 'ai_estimate_method')
    op.drop_column('bookings', 'ai_estimate_confidence')
    op.drop_column('bookings', 'ai_estimate_max')
    op.drop_column('bookings', 'ai_estimate_min')
    op.drop_column('bookings', 'matched_artisan_ids')
    op.drop_column('bookings', 'specialty_tags')
