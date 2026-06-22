import logging
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel

from app.core.config import settings
from app.core.auth import get_current_active_user, require_client
from app.models.user import User
from app.services.analysis_queue import analysis_queue_service
from app.services.media_storage import media_storage_service
from app.services.media_validation import media_validation_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs")


class JobIngestResponse(BaseModel):
    """Response schema for successful job ingestion"""
    job_id: str
    status: str
    message: str
    media_count: int
    analysis_queued: bool


class JobIngestRejectResponse(BaseModel):
    """Response schema for rejected job ingestion"""
    status: str
    rejected: bool
    errors: list[dict]
    message: str


@router.post("/ingest", response_model=JobIngestResponse, status_code=status.HTTP_201_CREATED)
async def ingest_job(
    current_user: User = Depends(require_client),
    service: str = Form(..., description="Service description"),
    location: Optional[str] = Form(None, description="Job location"),
    notes: Optional[str] = Form(None, description="Additional notes"),
    context: Optional[str] = Form(None, description="Context for media validation"),
    images: list[UploadFile] = File(default_factory=list, description="Image files"),
    videos: list[UploadFile] = File(default_factory=list, description="Video files"),
    audio: list[UploadFile] = File(default_factory=list, description="Audio/voice note files"),
):
    """
    Vision-to-Scope Ingestion Gateway
    
    Accepts multimodal job data (images, videos, voice notes) and performs
    AI-driven quality validation before allowing the booking to proceed.
    
    - Supports: JPEG/PNG/WEBP images, MP4 videos, MP3/WAV audio
    - Validates media quality using AI (GPT-4o or Claude 3.5)
    - Rejects sub-standard media with actionable feedback
    - Forwards validated payloads to Analysis Node queue
    """
    import uuid
    
    job_id = str(uuid.uuid4())
    
    # Validate total payload size
    total_size = 0
    max_total_size = settings.MEDIA_MAX_TOTAL_SIZE_MB * 1024 * 1024
    
    # Collect all files for size validation
    all_files = images + videos + audio
    
    for file in all_files:
        # Read file content to get size
        file_content = await file.read()
        total_size += len(file_content)
        # Reset file pointer for later reading
        await file.seek(0)
    
    if total_size > max_total_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Total payload size {total_size} bytes exceeds maximum of {max_total_size} bytes"
        )
    
    # Validate and process each media file
    validation_errors = []
    validated_media = []
    
    # Process images
    for idx, image in enumerate(images):
        try:
            # Validate file type
            if image.content_type not in settings.ALLOWED_IMAGE_TYPES:
                validation_errors.append({
                    "field": f"images[{idx}]",
                    "filename": image.filename,
                    "error": f"Invalid content type: {image.content_type}. Allowed: {settings.ALLOWED_IMAGE_TYPES}"
                })
                continue
            
            # Read file content
            image_content = await image.read()
            
            # Validate file size
            max_size = settings.MEDIA_MAX_SIZE_MB * 1024 * 1024
            if len(image_content) > max_size:
                validation_errors.append({
                    "field": f"images[{idx}]",
                    "filename": image.filename,
                    "error": f"File size exceeds maximum of {settings.MEDIA_MAX_SIZE_MB}MB"
                })
                continue
            
            # Store file
            storage_metadata = await media_storage_service.store_file(
                image_content,
                image.content_type,
                image.filename
            )
            
            # AI quality validation
            validation_result = await media_validation_service.validate_image(
                image_content,
                image.content_type,
                context
            )
            
            if not validation_result["is_valid"]:
                # Delete stored file if validation fails
                await media_storage_service.delete_file(storage_metadata["storage_key"])
                
                validation_errors.append({
                    "field": f"images[{idx}]",
                    "filename": image.filename,
                    "error": validation_result["feedback"],
                    "confidence": validation_result.get("confidence", 0.0)
                })
                continue
            
            validated_media.append({
                "type": "image",
                "storage_key": storage_metadata["storage_key"],
                "storage_type": storage_metadata["storage_type"],
                "content_type": image.content_type,
                "filename": image.filename,
                "size": storage_metadata["size"],
                "validation_confidence": validation_result.get("confidence", 0.0)
            })
            
        except Exception as e:
            logger.error(f"Error processing image {image.filename}: {e}")
            validation_errors.append({
                "field": f"images[{idx}]",
                "filename": image.filename,
                "error": f"Processing error: {str(e)}"
            })
    
    # Process videos
    for idx, video in enumerate(videos):
        try:
            # Validate file type
            if video.content_type not in settings.ALLOWED_VIDEO_TYPES:
                validation_errors.append({
                    "field": f"videos[{idx}]",
                    "filename": video.filename,
                    "error": f"Invalid content type: {video.content_type}. Allowed: {settings.ALLOWED_VIDEO_TYPES}"
                })
                continue
            
            # Read file content
            video_content = await video.read()
            
            # Validate file size
            max_size = settings.MEDIA_MAX_SIZE_MB * 1024 * 1024
            if len(video_content) > max_size:
                validation_errors.append({
                    "field": f"videos[{idx}]",
                    "filename": video.filename,
                    "error": f"File size exceeds maximum of {settings.MEDIA_MAX_SIZE_MB}MB"
                })
                continue
            
            # Store file
            storage_metadata = await media_storage_service.store_file(
                video_content,
                video.content_type,
                video.filename
            )
            
            # AI quality validation
            validation_result = await media_validation_service.validate_video(
                video_content,
                video.content_type,
                context
            )
            
            if not validation_result["is_valid"]:
                # Delete stored file if validation fails
                await media_storage_service.delete_file(storage_metadata["storage_key"])
                
                validation_errors.append({
                    "field": f"videos[{idx}]",
                    "filename": video.filename,
                    "error": validation_result["feedback"],
                    "confidence": validation_result.get("confidence", 0.0)
                })
                continue
            
            validated_media.append({
                "type": "video",
                "storage_key": storage_metadata["storage_key"],
                "storage_type": storage_metadata["storage_type"],
                "content_type": video.content_type,
                "filename": video.filename,
                "size": storage_metadata["size"],
                "validation_confidence": validation_result.get("confidence", 0.0)
            })
            
        except Exception as e:
            logger.error(f"Error processing video {video.filename}: {e}")
            validation_errors.append({
                "field": f"videos[{idx}]",
                "filename": video.filename,
                "error": f"Processing error: {str(e)}"
            })
    
    # Process audio
    for idx, audio_file in enumerate(audio):
        try:
            # Validate file type
            if audio_file.content_type not in settings.ALLOWED_AUDIO_TYPES:
                validation_errors.append({
                    "field": f"audio[{idx}]",
                    "filename": audio_file.filename,
                    "error": f"Invalid content type: {audio_file.content_type}. Allowed: {settings.ALLOWED_AUDIO_TYPES}"
                })
                continue
            
            # Read file content
            audio_content = await audio_file.read()
            
            # Validate file size
            max_size = settings.MEDIA_MAX_SIZE_MB * 1024 * 1024
            if len(audio_content) > max_size:
                validation_errors.append({
                    "field": f"audio[{idx}]",
                    "filename": audio_file.filename,
                    "error": f"File size exceeds maximum of {settings.MEDIA_MAX_SIZE_MB}MB"
                })
                continue
            
            # Store file
            storage_metadata = await media_storage_service.store_file(
                audio_content,
                audio_file.content_type,
                audio_file.filename
            )
            
            # AI quality validation
            validation_result = await media_validation_service.validate_audio(
                audio_content,
                audio_file.content_type,
                context
            )
            
            if not validation_result["is_valid"]:
                # Delete stored file if validation fails
                await media_storage_service.delete_file(storage_metadata["storage_key"])
                
                validation_errors.append({
                    "field": f"audio[{idx}]",
                    "filename": audio_file.filename,
                    "error": validation_result["feedback"],
                    "confidence": validation_result.get("confidence", 0.0)
                })
                continue
            
            validated_media.append({
                "type": "audio",
                "storage_key": storage_metadata["storage_key"],
                "storage_type": storage_metadata["storage_type"],
                "content_type": audio_file.content_type,
                "filename": audio_file.filename,
                "size": storage_metadata["size"],
                "validation_confidence": validation_result.get("confidence", 0.0)
            })
            
        except Exception as e:
            logger.error(f"Error processing audio {audio_file.filename}: {e}")
            validation_errors.append({
                "field": f"audio[{idx}]",
                "filename": audio_file.filename,
                "error": f"Processing error: {str(e)}"
            })
    
    # Rejection Gate: If there are validation errors, reject the payload
    if validation_errors:
        # Clean up any successfully stored files
        for media in validated_media:
            try:
                await media_storage_service.delete_file(media["storage_key"])
            except Exception as e:
                logger.error(f"Error cleaning up file {media['storage_key']}: {e}")
        
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "rejected",
                "rejected": True,
                "errors": validation_errors,
                "message": "Media validation failed. Please address the errors and resubmit."
            }
        )
    
    # At least one media file is required
    if not validated_media:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one media file (image, video, or audio) is required"
        )
    
    # Build payload for Analysis Node
    analysis_payload = {
        "job_id": job_id,
        "user_id": str(current_user.id),
        "service": service,
        "location": location,
        "notes": notes,
        "context": context,
        "media": validated_media,
        "submitted_at": None  # Will be set by queue service
    }
    
    # Enqueue for analysis
    queue_success = await analysis_queue_service.enqueue_payload(analysis_payload)
    
    if not queue_success:
        # Clean up stored files if queue fails
        for media in validated_media:
            try:
                await media_storage_service.delete_file(media["storage_key"])
            except Exception as e:
                logger.error(f"Error cleaning up file {media['storage_key']}: {e}")
        
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Analysis queue service unavailable. Please try again later."
        )
    
    logger.info(f"Job {job_id} successfully ingested and queued for analysis")
    
    return JobIngestResponse(
        job_id=job_id,
        status="queued_for_analysis",
        message="Job successfully ingested and queued for analysis",
        media_count=len(validated_media),
        analysis_queued=True
    )
