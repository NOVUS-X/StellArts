import os
import shutil
import uuid

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.core.cache import cache
from app.core.config import settings
from app.core.exceptions import AppException
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

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


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
