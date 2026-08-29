# cursor_store.py
from sqlalchemy import text
from sqlalchemy.orm import Session

CURSOR_KEY = "soroban_event_cursor"


def get_cursor(db: Session) -> str:
    result = db.execute(
        text("SELECT value FROM worker_state WHERE key = :key"), {"key": CURSOR_KEY}
    )
    row = result.fetchone()
    return row[0] if row else "0"


def save_cursor(db: Session, event_id: str) -> None:
    db.execute(
        text(
            """
            INSERT INTO worker_state (key, value)
            VALUES (:key, :value)
            ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value
        """
        ),
        {"key": CURSOR_KEY, "value": event_id},
    )
