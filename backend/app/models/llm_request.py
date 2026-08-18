from sqlalchemy import Column, Integer, String, Text, DateTime
from sqlalchemy.sql import func

from app.db.base import Base


class LLMRequest(Base):
    """Track LLM API requests for monitoring and cost analysis"""
    
    __tablename__ = "llm_requests"
    
    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(String(50), unique=True, nullable=False, index=True)
    provider = Column(String(20), nullable=False)  # 'openai' or 'gemini'
    operation = Column(String(50), nullable=False)  # 'extract_specialties' or 'estimate_price'
    input_length = Column(Integer, nullable=True)
    status = Column(String(20), nullable=False)  # 'success', 'error', 'rate_limited'
    response_time_ms = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    retries = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
