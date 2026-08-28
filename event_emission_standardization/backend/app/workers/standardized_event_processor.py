# standardized_event_processor.py
"""
Standardized Event Processor for FastAPI backend and indexer services.
Consumes contract events matching the schema:
Topics: ["Escrow", "<Action>", <engagement_id>]
"""

import logging
from typing import Any, Dict, Optional
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Map standardized action symbols to internal booking status values
ACTION_TO_BOOKING_STATUS = {
    "Initialized": "pending",
    "Funded": "funded",
    "MaterialsReleased": "in_progress",
    "Released": "completed",
    "MilestoneReleased": "in_progress",
    "Reclaimed": "reclaimed",
    "Disputed": "disputed",
    "Resolved": "resolved",
}


def extract_event_metadata(event: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extracts standardized domain, action, and engagement_id from event topics and payload.
    Supports parsed event dicts or raw RPC responses.
    """
    topics = event.get("topics", [])
    domain = topics[0] if len(topics) > 0 else event.get("domain")
    action = topics[1] if len(topics) > 1 else event.get("action")
    engagement_id = topics[2] if len(topics) > 2 else event.get("engagement_id")
    
    value = event.get("value", {})
    if not engagement_id and isinstance(value, dict):
        engagement_id = value.get("engagement_id") or value.get("id")

    return {
        "domain": domain,
        "action": action,
        "engagement_id": engagement_id,
        "payload": value,
        "event_id": event.get("id"),
        "ledger": event.get("ledger"),
    }


def process_standardized_event(db: Session, raw_event: Dict[str, Any]) -> bool:
    """
    Idempotently processes a standardized Soroban escrow event against the database.
    """
    meta = extract_event_metadata(raw_event)
    domain = meta["domain"]
    action = meta["action"]
    engagement_id = meta["engagement_id"]
    event_id = meta["event_id"]

    # Filter for Escrow domain
    if domain != "Escrow":
        logger.debug(f"Ignoring non-escrow domain event: {domain}:{action}")
        return True

    new_status = ACTION_TO_BOOKING_STATUS.get(action)
    if not new_status:
        logger.info(f"No database state transition for action: {action}")
        return True

    if not engagement_id:
        logger.warning(f"Could not resolve engagement_id for event: {event_id}")
        return False

    # Execute idempotent status update
    stmt = text(
        """
        UPDATE bookings
        SET status = :status,
            processed_event_id = :event_id,
            updated_at = CURRENT_TIMESTAMP
        WHERE engagement_id = :engagement_id
          AND (processed_event_id IS NULL OR processed_event_id != :event_id)
        """
    )
    result = db.execute(
        stmt,
        {
            "status": new_status,
            "engagement_id": engagement_id,
            "event_id": event_id,
        },
    )

    if result.rowcount == 0:
        logger.info(
            f"Event {event_id} for engagement {engagement_id} skipped (already processed or not found)."
        )
    else:
        logger.info(
            f"Successfully updated engagement {engagement_id} to status '{new_status}' via event {event_id}."
        )

    return True
