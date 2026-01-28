from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base import Base


class Portfolio(Base):
    __tablename__ = "portfolios"
    __table_args__ = (
        Index("idx_portfolio_artisan_created", "artisan_id", "created_at"),
    )

    id = Column(Integer, primary_key=True, index=True)
    artisan_id = Column(Integer, ForeignKey("artisans.id"), nullable=False)
    title = Column(String(200), nullable=True)
    image = Column(String(500), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    artisan = relationship("Artisan", back_populates="portfolio_items")
