"""add job specialties to bookings

Revision ID: c1d2e3f4a5b6
Revises: 1a2b3c4d5e6f
"""

from alembic import op
import sqlalchemy as sa

revision = "c1d2e3f4a5b6"
down_revision = "1a2b3c4d5e6f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("bookings", sa.Column("job_specialties", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("bookings", "job_specialties")
