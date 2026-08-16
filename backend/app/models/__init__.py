# Import database components
from app.db.base import Base
from app.models.notification import Notification

# Re-export for convenience
__all__ = ["Base", "Notification"]
