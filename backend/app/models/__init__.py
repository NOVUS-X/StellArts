# Import database components
from app.db.base import Base

# Register all models so Alembic / Base.metadata picks them up
from app.models.artisan import Artisan  # noqa: F401
from app.models.booking import Booking  # noqa: F401
from app.models.client import Client  # noqa: F401
from app.models.inventory_check_result import InventoryCheckResult  # noqa: F401
from app.models.payment import Payment  # noqa: F401
from app.models.portfolio import Portfolio  # noqa: F401
from app.models.store import Store  # noqa: F401
from app.models.user import User  # noqa: F401

# Re-export for convenience
__all__ = [
    "Base",
    "Artisan",
    "Booking",
    "Client",
    "InventoryCheckResult",
    "Payment",
    "Portfolio",
    "Store",
    "User",
]
