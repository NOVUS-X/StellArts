"""Add artisan_calendar_tokens and calendar_events tables

Revision ID: 002_add_calendar_tables
Revises: 001_pgvector_embedding
Create Date: 2026-03-28
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "002_add_calendar_tables"
down_revision = "001_pgvector_embedding"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    # ── artisan_calendar_tokens ───────────────────────────────────────────────
    if "artisan_calendar_tokens" not in existing_tables:
        op.create_table(
            "artisan_calendar_tokens",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column(
                "artisan_id",
                sa.Integer(),
                sa.ForeignKey("artisans.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column("provider", sa.String(20), nullable=False),
            sa.Column("access_token", sa.Text(), nullable=False),
            sa.Column("refresh_token", sa.Text(), nullable=True),
            sa.Column("token_expiry", sa.DateTime(timezone=True), nullable=True),
            sa.Column("scope", sa.Text(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                onupdate=sa.func.now(),
            ),
        )

    # ── calendar_events ───────────────────────────────────────────────────────
    if "calendar_events" not in existing_tables:
        op.create_table(
            "calendar_events",
            sa.Column("id", sa.Uuid(), primary_key=True, index=True),
            sa.Column(
                "artisan_id",
                sa.Integer(),
                sa.ForeignKey("artisans.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column("provider", sa.String(20), nullable=False),
            sa.Column("external_id", sa.String(500), nullable=False),
            sa.Column("title", sa.String(500), nullable=True),
            sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
            sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
            sa.Column("location", sa.Text(), nullable=True),
            sa.Column("latitude", sa.String(20), nullable=True),
            sa.Column("longitude", sa.String(20), nullable=True),
            sa.Column("is_busy", sa.Boolean(), default=True),
            sa.Column(
                "synced_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if "calendar_events" in existing_tables:
        op.drop_table("calendar_events")

    if "artisan_calendar_tokens" in existing_tables:
        op.drop_table("artisan_calendar_tokens")
