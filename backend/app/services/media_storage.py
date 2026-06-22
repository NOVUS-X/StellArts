import os
import uuid
from pathlib import Path
from typing import Optional

import boto3
from botocore.exceptions import ClientError

from app.core.config import settings


class MediaStorageService:
    """
    Service for secure temporary storage of media files.
    Supports local filesystem and S3 storage backends.
    """

    def __init__(self):
        self.storage_type = settings.MEDIA_STORAGE_TYPE
        self.temp_dir = Path(settings.MEDIA_TEMP_DIR)
        
        # Initialize local storage
        if self.storage_type == "local":
            self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize S3 storage
        elif self.storage_type == "s3":
            if not settings.AWS_S3_BUCKET:
                raise ValueError("AWS_S3_BUCKET must be set when MEDIA_STORAGE_TYPE is 's3'")
            
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_REGION
            )
            self.bucket = settings.AWS_S3_BUCKET
            self.prefix = settings.AWS_S3_PREFIX

    async def store_file(
        self,
        file_content: bytes,
        content_type: str,
        filename: Optional[str] = None
    ) -> dict:
        """
        Store a file securely and return metadata including storage path/URL.
        
        Args:
            file_content: Raw file bytes
            content_type: MIME type of the file
            filename: Original filename (optional)
            
        Returns:
            dict with storage metadata including 'storage_key', 'storage_type', 'size'
        """
        file_size = len(file_content)
        
        # Validate file size
        max_size_bytes = settings.MEDIA_MAX_SIZE_MB * 1024 * 1024
        if file_size > max_size_bytes:
            raise ValueError(
                f"File size {file_size} bytes exceeds maximum allowed size of {max_size_bytes} bytes"
            )
        
        # Generate unique storage key
        file_extension = self._get_extension_from_mime(content_type)
        unique_id = str(uuid.uuid4())
        storage_key = f"{unique_id}{file_extension}"
        
        if self.storage_type == "local":
            return await self._store_local(file_content, storage_key, file_size)
        elif self.storage_type == "s3":
            return await self._store_s3(file_content, storage_key, content_type, file_size)
        else:
            raise ValueError(f"Unsupported storage type: {self.storage_type}")

    async def _store_local(
        self,
        file_content: bytes,
        storage_key: str,
        file_size: int
    ) -> dict:
        """Store file in local temporary directory."""
        file_path = self.temp_dir / storage_key
        
        try:
            with open(file_path, 'wb') as f:
                f.write(file_content)
            
            return {
                "storage_key": storage_key,
                "storage_type": "local",
                "size": file_size,
                "path": str(file_path)
            }
        except IOError as e:
            raise IOError(f"Failed to store file locally: {e}")

    async def _store_s3(
        self,
        file_content: bytes,
        storage_key: str,
        content_type: str,
        file_size: int
    ) -> dict:
        """Store file in S3 bucket."""
        s3_key = f"{self.prefix}{storage_key}"
        
        try:
            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=s3_key,
                Body=file_content,
                ContentType=content_type
            )
            
            # Generate presigned URL (valid for 1 hour)
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket, 'Key': s3_key},
                ExpiresIn=3600
            )
            
            return {
                "storage_key": s3_key,
                "storage_type": "s3",
                "size": file_size,
                "url": url,
                "bucket": self.bucket
            }
        except ClientError as e:
            raise IOError(f"Failed to store file in S3: {e}")

    async def delete_file(self, storage_key: str) -> bool:
        """
        Delete a file from storage.
        
        Args:
            storage_key: The storage key returned from store_file
            
        Returns:
            True if deletion was successful
        """
        if self.storage_type == "local":
            file_path = self.temp_dir / storage_key
            try:
                if file_path.exists():
                    file_path.unlink()
                    return True
                return False
            except IOError:
                return False
        
        elif self.storage_type == "s3":
            try:
                self.s3_client.delete_object(Bucket=self.bucket, Key=storage_key)
                return True
            except ClientError:
                return False
        
        return False

    async def get_file(self, storage_key: str) -> Optional[bytes]:
        """
        Retrieve file content from storage.
        
        Args:
            storage_key: The storage key returned from store_file
            
        Returns:
            File bytes or None if not found
        """
        if self.storage_type == "local":
            file_path = self.temp_dir / storage_key
            try:
                if file_path.exists():
                    with open(file_path, 'rb') as f:
                        return f.read()
                return None
            except IOError:
                return None
        
        elif self.storage_type == "s3":
            try:
                response = self.s3_client.get_object(Bucket=self.bucket, Key=storage_key)
                return response['Body'].read()
            except ClientError:
                return None
        
        return None

    def _get_extension_from_mime(self, mime_type: str) -> str:
        """Map MIME type to file extension."""
        mime_to_ext = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
            "video/mp4": ".mp4",
            "audio/mpeg": ".mp3",
            "audio/wav": ".wav",
            "audio/mp3": ".mp3"
        }
        return mime_to_ext.get(mime_type, ".bin")


# Singleton instance
media_storage_service = MediaStorageService()
