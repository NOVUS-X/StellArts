"""add_jobs_table_with_work_proof_hash

Revision ID: a1b2c3d4e5f6
Revises: 45a54bec1cb4
Create Date: 2026-07-23 20:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '45a54bec1cb4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'jobs',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('ingest_job_id', sa.String(length=255), nullable=True),
        sa.Column('after_image_url', sa.String(length=1000), nullable=True),
        # SHA-256 hex digest (64 chars) of the raw "After" image bytes.
        # Provides a tamper-evident cryptographic proof of completed work.
        sa.Column('work_proof_hash', sa.String(length=64), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='completed'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_jobs_id'), 'jobs', ['id'], unique=False)
    op.create_index(op.f('ix_jobs_ingest_job_id'), 'jobs', ['ingest_job_id'], unique=False)
    op.create_index(op.f('ix_jobs_work_proof_hash'), 'jobs', ['work_proof_hash'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_jobs_work_proof_hash'), table_name='jobs')
    op.drop_index(op.f('ix_jobs_ingest_job_id'), table_name='jobs')
    op.drop_index(op.f('ix_jobs_id'), table_name='jobs')
    op.drop_table('jobs')
