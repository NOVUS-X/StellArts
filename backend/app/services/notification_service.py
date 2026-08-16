import logging

from sqlalchemy.orm import Session

from app.core.websocket import manager
from app.models.notification import Notification

logger = logging.getLogger(__name__)


async def create_notification(
    db: Session,
    user_id: int,
    type: str,
    title: str,
    message: str,
    reference_id: str | None = None,
) -> Notification:
    """
    Creates a persistent Notification record in DB and broadcasts it via WebSocket
    if the user is currently online.
    """
    notification = Notification(
        user_id=user_id,
        type=type,
        title=title,
        message=message,
        reference_id=str(reference_id) if reference_id is not None else None,
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)

    # Prepare JSON payload for WebSocket
    payload = {
        "id": str(notification.id),
        "user_id": notification.user_id,
        "type": notification.type,
        "title": notification.title,
        "message": notification.message,
        "is_read": notification.is_read,
        "read": notification.is_read,
        "reference_id": notification.reference_id,
        "created_at": (
            notification.created_at.isoformat() if notification.created_at else None
        ),
        "updated_at": (
            notification.updated_at.isoformat() if notification.updated_at else None
        ),
    }

    try:
        await manager.send_personal_message(payload, user_id)
    except Exception as e:
        logger.warning(f"Could not send real-time notification to user {user_id}: {e}")

    return notification


async def dispatch_to_matched_artisans(db: Session, booking) -> None:
    """
    Dispatches notifications to the artisan assigned to a new booking.
    """
    try:
        if booking and booking.artisan and booking.artisan.user_id:
            await create_notification(
                db=db,
                user_id=booking.artisan.user_id,
                type="booking_created",
                title="New Booking Request",
                message=f"You have received a new booking request for '{booking.service}'.",
                reference_id=str(booking.id),
            )
    except Exception as e:
        logger.warning(f"Failed in dispatch_to_matched_artisans: {e}")
