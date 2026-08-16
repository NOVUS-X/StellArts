# Import database components
from app.db.base import Base
from app.models.notification import Notification
from app.models.message import Message

# Re-export for convenience
__all__ = ["Base", "Notification", "Message"]
