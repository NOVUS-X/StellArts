"""
Migration to add events table for tracking on-chain events.

This table stores Soroban events with their processing status
and cursor information for idempotent event handling.
"""

from sqlalchemy import (
    Column,
    String,
    DateTime,
    Text,
    Boolean,
    Index,
    func,
)
from app.db.base import Base
def upgrade():
    """Create events table."""
    events_table = Table(
        "events",
        Base.metadata,
        Column("id", String(64), primary_key=True, index=True),
        Column("transaction_hash", String(64), nullable=False, index=True),
        Column("contract_address", String(64), nullable=False, index=True),
        Column("topic", String(128), nullable=False, index=True),
        Column("body", Text, nullable=False),
        Column("ledger_sequence", Integer, nullable=False, index=True),
        Column("created_at", DateTime(timezone=True), server_default=func.now()),
        Column("processed_at", DateTime(timezone=True), nullable=True),
        Column("processing_status", String(20), default="pending"),
        Column("error_message", Text, nullable=True),
        Column("retry_count", Integer, default=0),
    )
    
    # Index for efficient lookup of unprocessed events
    Index(
        "ix_events_unprocessed",
        events_table.c.contract_address,
        events_table.c.topic,
        events_table.c.processing_status,
    )
    
    # Index for cursor-based pagination
    Index(
        "ix_events_cursor",
        events_table.c.contract_address,
        events_table.c.ledger_sequence,
    )

    events_table.create(checkfirst=True)
    logger.info("Events table created successfully")
def downgrade():
    """Drop events table."""
    events_table = Table(
        "events",
        Base.metadata,
    )
    events_table.drop(checkfirst=True)
    logger.info("Events table dropped successfully")
from sqlalchemy import Table, Column, String, DateTime, Text, Boolean, Index, func
from app.db.base import Base
import logging

logger = logging.getLogger(__name__)
