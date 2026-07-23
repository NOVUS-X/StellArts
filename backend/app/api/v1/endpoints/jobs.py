import hashlib
import os
import shutil
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.cache import cache
from app.core.config import settings
from app.core.exceptions import AppException
from app.db.session import get_db
from app.models.job import Job
from app.services.ai_service import ai_service

router = APIRouter()

ALLOWED_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "video/mp4",
    "audio/mpeg",
    "audio/wav",
    "audio/x-wav",
}

ALLOWED_IMAGE_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
}

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


# ---------------------------------------------------------------------------
# Response schema
# ---------------------------------------------------------------------------


class JobResponse(BaseModel):
    id: str
    ingest_job_id: str | None
    after_image_url: str | None
    work_proof_hash: str | None
    status: str
    notes: str | None

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/ingest", status_code=status.HTTP_202_ACCEPTED)
async def ingest_job(
    title: str = Form(...),
    description: str | None = Form(None),
    files: list[UploadFile] = File(...),
):
    """
    Vision-to-Scope ingestion gateway.
    Accepts multimodal payloads, evaluates media via AI, and forwards to Analysis Node queue.
    """
    if not files:
        raise HTTPException(status_code=400, detail="No media files provided.")

    saved_files = []

    # Ensure tmp directory exists
    tmp_dir = os.path.join(os.getcwd(), settings.STATIC_DIR, "tmp")
    os.makedirs(tmp_dir, exist_ok=True)

    try:
        for file in files:
            # 1. Basic security & size validation
            if file.content_type not in ALLOWED_MIME_TYPES:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported file type: {file.content_type}. Allowed: {', '.join(ALLOWED_MIME_TYPES)}",
                )

            # Move cursor to end to get size
            file.file.seek(0, 2)
            file_size = file.file.tell()
            file.file.seek(0)

            if file_size > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=400,
                    detail=f"File {file.filename} exceeds maximum size of {MAX_FILE_SIZE} bytes.",
                )

            # 2. Save file temporarily
            ext = os.path.splitext(file.filename)[1] if file.filename else ""
            unique_filename = f"{uuid.uuid4()}{ext}"
            file_path = os.path.join(tmp_dir, unique_filename)

            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            saved_files.append({"path": file_path, "original_name": file.filename})

        # 3. AI Quality Validation Gate
        for saved_file in saved_files:
            ai_result = await ai_service.validate_media_quality(
                saved_file["path"], saved_file["original_name"]
            )

            if not ai_result["is_valid"]:
                # If rejected, clean up files and return 400 with actionable feedback
                for f in saved_files:
                    if os.path.exists(f["path"]):
                        os.remove(f["path"])

                raise AppException(
                    message="Media Quality Validation Failed",
                    error_code="media_validation_failed",
                    status_code=400,
                    details={
                        "feedback": ai_result["feedback"],
                        "file": saved_file["original_name"],
                    },
                )

        # 4. Forward to Analysis Node queue
        job_payload = {
            "job_id": str(uuid.uuid4()),
            "title": title,
            "description": description,
            "media_files": [f["path"] for f in saved_files],
            "status": "pending_analysis",
        }

        # Enqueue job to Redis
        queued = await cache.lpush("analysis_node_queue", job_payload)

        if not queued:
            raise HTTPException(
                status_code=500, detail="Failed to enqueue job for analysis."
            )

        return {
            "message": "Job successfully ingested and queued for analysis.",
            "job_id": job_payload["job_id"],
        }

    except (HTTPException, AppException):
        raise
    except Exception as e:
        # Cleanup on unexpected errors
        for f in saved_files:
            if os.path.exists(f["path"]):
                os.remove(f["path"])
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post(
    "/complete",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit job completion with 'After' photo",
    description=(
        "Artisan uploads an 'After' photo to mark a job as complete. "
        "The backend generates a SHA-256 hash of the raw file bytes and persists "
        "it alongside the image URL so the completion can be audited later."
    ),
)
async def complete_job(
    ingest_job_id: str = Form(..., description="The job_id returned by /ingest"),
    notes: str | None = Form(None, description="Optional completion notes"),
    after_image: UploadFile = File(..., description="The 'After' photo of the completed work"),
    db: Session = Depends(get_db),
):
    """
    Record job completion with a cryptographic proof of the uploaded 'After' photo.

    Steps:
    1. Validate the uploaded image type and size.
    2. Read the full file buffer into memory.
    3. Compute a SHA-256 hex digest of the raw bytes — this is the work_proof_hash.
    4. Persist the image to disk and record the URL + hash in the database.
    5. Return the created Job record.
    """
    # --- 1. Validate mime type ---
    if after_image.content_type not in ALLOWED_IMAGE_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported file type: {after_image.content_type}. "
                f"Allowed image types: {', '.join(sorted(ALLOWED_IMAGE_MIME_TYPES))}"
            ),
        )

    # --- 2. Read full buffer & validate size ---
    file_bytes = await after_image.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File exceeds maximum allowed size of {MAX_FILE_SIZE} bytes.",
        )

    # --- 3. Compute SHA-256 hash of the raw file bytes ---
    work_proof_hash = hashlib.sha256(file_bytes).hexdigest()

    # --- 4. Persist image to disk ---
    upload_dir = os.path.join(os.getcwd(), settings.STATIC_DIR, "after_images")
    os.makedirs(upload_dir, exist_ok=True)

    ext = os.path.splitext(after_image.filename)[1] if after_image.filename else ".jpg"
    unique_filename = f"{uuid.uuid4()}{ext}"
    file_path = os.path.join(upload_dir, unique_filename)

    try:
        with open(file_path, "wb") as buffer:
            buffer.write(file_bytes)
    except OSError as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to save uploaded file: {e}"
        ) from e

    # Build a relative URL that can be served by a static file handler
    after_image_url = f"/{settings.STATIC_DIR}/after_images/{unique_filename}"

    # --- 5. Persist Job record to database ---
    job = Job(
        ingest_job_id=ingest_job_id,
        after_image_url=after_image_url,
        work_proof_hash=work_proof_hash,
        status="completed",
        notes=notes,
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    return JobResponse(
        id=str(job.id),
        ingest_job_id=job.ingest_job_id,
        after_image_url=job.after_image_url,
        work_proof_hash=job.work_proof_hash,
        status=job.status,
        notes=job.notes,
    )


@router.get(
    "/{job_id}",
    response_model=JobResponse,
    summary="Retrieve a completed job record",
    description="Returns the job record including the work_proof_hash for auditing.",
)
def get_job(job_id: str, db: Session = Depends(get_db)):
    """
    Fetch a job completion record by its UUID.

    The `work_proof_hash` field contains the SHA-256 hex digest of the original
    uploaded 'After' image bytes, which can be used to verify the file has not
    been tampered with since upload.
    """
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job '{job_id}' not found.",
        )

    return JobResponse(
        id=str(job.id),
        ingest_job_id=job.ingest_job_id,
        after_image_url=job.after_image_url,
        work_proof_hash=job.work_proof_hash,
        status=job.status,
        notes=job.notes,
    )
