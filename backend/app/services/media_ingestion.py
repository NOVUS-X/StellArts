from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile
from PIL import Image, ImageFilter, ImageStat

from app.core.config import settings
from app.schemas.ingestion import StoredMedia, ValidationFeedback

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_VIDEO_TYPES = {"video/mp4", "video/quicktime", "video/webm"}
ALLOWED_AUDIO_TYPES = {
    "audio/mpeg",
    "audio/mp3",
    "audio/mp4",
    "audio/wav",
    "audio/x-wav",
    "audio/webm",
    "audio/ogg",
    "audio/aac",
}


@dataclass
class IngestionResult:
    stored_media: list[StoredMedia]
    feedback: list[ValidationFeedback]

    @property
    def accepted(self) -> bool:
        return not self.feedback


class MediaIngestionService:
    def __init__(self) -> None:
        self.storage_root = Path(settings.INGESTION_STORAGE_DIR)

    async def process(
        self,
        *,
        job_id: str,
        photos: list[UploadFile],
        videos: list[UploadFile],
        voice_notes: list[UploadFile],
    ) -> IngestionResult:
        stored_media: list[StoredMedia] = []
        feedback: list[ValidationFeedback] = []

        if not any([photos, videos, voice_notes]):
            feedback.append(
                ValidationFeedback(
                    code="empty_payload",
                    message="Add at least one photo, video, or voice note before submitting.",
                    media_type="photo",
                )
            )
            return IngestionResult(stored_media=stored_media, feedback=feedback)

        for photo in photos:
            result = await self._handle_photo(job_id, photo)
            if isinstance(result, ValidationFeedback):
                feedback.append(result)
            else:
                stored_media.append(result)

        for video in videos:
            result = await self._handle_binary_media(
                job_id=job_id,
                upload=video,
                media_type="video",
                allowed_types=ALLOWED_VIDEO_TYPES,
                min_size=settings.INGESTION_MIN_VIDEO_BYTES,
                too_small_message=(
                    "The video is too short or heavily compressed. Please upload a clearer, higher-resolution clip."
                ),
            )
            if isinstance(result, ValidationFeedback):
                feedback.append(result)
            else:
                stored_media.append(result)

        for voice_note in voice_notes:
            result = await self._handle_binary_media(
                job_id=job_id,
                upload=voice_note,
                media_type="voice",
                allowed_types=ALLOWED_AUDIO_TYPES,
                min_size=settings.INGESTION_MIN_AUDIO_BYTES,
                too_small_message=(
                    "The voice note is too short or silent. Please re-record with a clearer description of the work scope."
                ),
            )
            if isinstance(result, ValidationFeedback):
                feedback.append(result)
            else:
                stored_media.append(result)

        if feedback:
            self._cleanup(job_id)
            stored_media = []

        return IngestionResult(stored_media=stored_media, feedback=feedback)

    async def _handle_photo(
        self, job_id: str, upload: UploadFile
    ) -> StoredMedia | ValidationFeedback:
        if upload.content_type not in ALLOWED_IMAGE_TYPES:
            return ValidationFeedback(
                code="unsupported_photo_type",
                message="Upload photos as JPEG, PNG, or WEBP files.",
                media_type="photo",
                filename=upload.filename,
            )

        payload = await upload.read()
        if len(payload) < settings.INGESTION_MIN_IMAGE_BYTES:
            return ValidationFeedback(
                code="photo_too_small",
                message="This photo is too compressed to assess the job. Please upload a higher-resolution image.",
                media_type="photo",
                filename=upload.filename,
            )

        try:
            image = Image.open(BytesIO(payload)).convert("L")
        except Exception:
            return ValidationFeedback(
                code="invalid_photo",
                message="We couldn't read this photo. Please upload it again as a clear image file.",
                media_type="photo",
                filename=upload.filename,
            )

        width, height = image.size
        if (
            width < settings.INGESTION_MIN_IMAGE_WIDTH
            or height < settings.INGESTION_MIN_IMAGE_HEIGHT
        ):
            return ValidationFeedback(
                code="photo_low_resolution",
                message="The photo resolution is too low. Please retake it so the full work area is visible in high resolution.",
                media_type="photo",
                filename=upload.filename,
            )

        brightness = ImageStat.Stat(image).mean[0]
        if brightness < settings.INGESTION_MIN_BRIGHTNESS:
            return ValidationFeedback(
                code="photo_too_dark",
                message="I can't make out enough detail because the lighting is too low. Please retake the photo with better lighting and include the full area.",
                media_type="photo",
                filename=upload.filename,
            )

        edge_image = image.filter(ImageFilter.FIND_EDGES)
        edge_stddev = ImageStat.Stat(edge_image).stddev[0]
        sharpness = math.sqrt(edge_stddev) * 4
        if sharpness < settings.INGESTION_MIN_SHARPNESS:
            return ValidationFeedback(
                code="photo_too_blurry",
                message="I can't clearly see the work surface because the photo is blurry. Could you snap another photo from a steadier angle?",
                media_type="photo",
                filename=upload.filename,
            )

        metadata = {
            "width": width,
            "height": height,
            "brightness": round(brightness, 2),
            "sharpness": round(sharpness, 2),
        }
        return self._store_media(
            job_id=job_id,
            media_type="photo",
            upload=upload,
            payload=payload,
            metadata=metadata,
        )

    async def _handle_binary_media(
        self,
        *,
        job_id: str,
        upload: UploadFile,
        media_type: str,
        allowed_types: set[str],
        min_size: int,
        too_small_message: str,
    ) -> StoredMedia | ValidationFeedback:
        if upload.content_type not in allowed_types:
            return ValidationFeedback(
                code=f"unsupported_{media_type}_type",
                message=f"Unsupported {media_type} format. Please upload a standard file type.",
                media_type=media_type,
                filename=upload.filename,
            )

        payload = await upload.read()
        if len(payload) < min_size:
            return ValidationFeedback(
                code=f"{media_type}_too_small",
                message=too_small_message,
                media_type=media_type,
                filename=upload.filename,
            )

        return self._store_media(
            job_id=job_id,
            media_type=media_type,
            upload=upload,
            payload=payload,
            metadata={"size_bytes": len(payload)},
        )

    def _store_media(
        self,
        *,
        job_id: str,
        media_type: str,
        upload: UploadFile,
        payload: bytes,
        metadata: dict[str, float | int | str | bool | None],
    ) -> StoredMedia:
        job_dir = self.storage_root / job_id / media_type
        job_dir.mkdir(parents=True, exist_ok=True)
        filename = self._safe_filename(upload.filename, media_type)
        destination = job_dir / filename
        destination.write_bytes(payload)

        return StoredMedia(
            media_type=media_type,
            filename=filename,
            content_type=upload.content_type or "application/octet-stream",
            size_bytes=len(payload),
            storage_path=str(destination),
            metadata=metadata,
        )

    def _cleanup(self, job_id: str) -> None:
        job_dir = self.storage_root / job_id
        if not job_dir.exists():
            return

        for path in sorted(job_dir.rglob("*"), reverse=True):
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                path.rmdir()
        if job_dir.exists():
            job_dir.rmdir()

    def _safe_filename(self, original_name: str | None, media_type: str) -> str:
        suffix = Path(original_name or "").suffix or self._default_extension(media_type)
        stem = Path(original_name or media_type).stem or media_type
        sanitized_stem = "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in stem)
        return f"{sanitized_stem}-{uuid4().hex[:8]}{suffix.lower()}"

    def _default_extension(self, media_type: str) -> str:
        return {
            "photo": ".jpg",
            "video": ".mp4",
            "voice": ".m4a",
        }[media_type]


def build_job_payload(
    *,
    job_id: str,
    session_id: str | None,
    client_reference: str | None,
    stored_media: list[StoredMedia],
) -> dict:
    return {
        "job_id": job_id,
        "session_id": session_id,
        "client_reference": client_reference,
        "created_at": datetime.now(UTC).isoformat(),
        "media": [item.model_dump() for item in stored_media],
        "status": "queued_for_analysis",
    }


media_ingestion_service = MediaIngestionService()
