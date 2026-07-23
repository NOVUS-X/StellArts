import uuid

from sqlalchemy import Column, DateTime, String, Text, Uuid
from sqlalchemy.sql import func

from app.db.base import Base


class Job(Base):
    """
    Represents a completed job record with a cryptographic proof of work.

    When an artisan uploads an "After" photo to prove job completion, a SHA-256
    hash of the image buffer is computed and stored in `work_proof_hash` for
    tamper-evident auditing.
    """

    __tablename__ = "jobs"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4, index=True)

    # Reference to the ingested job ID from the analysis queue
    ingest_job_id = Column(String(255), nullable=True, index=True)

    # URL/path of the uploaded "After" photo
    after_image_url = Column(String(1000), nullable=True)

    # SHA-256 hex digest of the raw file bytes — cryptographic proof of work
    work_proof_hash = Column(String(64), nullable=True, index=True)

    # Status of the job record
    status = Column(String(50), nullable=False, default="completed")

    # Optional free-text notes attached at completion time
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
