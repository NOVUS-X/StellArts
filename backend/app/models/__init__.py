# Import database components
from app.db.base import Base

# Import all models to ensure they're registered with Base
from app.models.user import User
from app.models.artisan import Artisan
from app.models.client import Client
from app.models.booking import Booking
from app.models.payment import Payment, PaymentAudit, PaymentAuditEventType
from app.models.review import Review
from app.models.portfolio import Portfolio
from app.models.notification import Notification

# Re-export for convenience
__all__ = ["Base", "User", "Artisan", "Client", "Booking", "Payment", "PaymentAudit", "PaymentAuditEventType", "Review", "Portfolio", "Notification"]
