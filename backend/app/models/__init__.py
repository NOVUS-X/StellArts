# Import database components
from app.db.base import Base

# Re-export for convenience
__all__ = ["Base"]

# Register all models so they are available via this package
from app.models.store import Store  # noqa: F401
from app.models.inventory_check_run import InventoryCheckRun  # noqa: F401
from app.models.inventory_notification import InventoryNotification  # noqa: F401
