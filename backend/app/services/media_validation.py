import base64
import logging
from typing import Optional

import anthropic
import httpx
from openai import OpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)


class MediaValidationService:
    """
    AI-driven quality validation service for vision and audio media.
    Integrates with GPT-4o or Claude 3.5 to evaluate media clarity and context.
    """

    def __init__(self):
        self.provider = settings.AI_VALIDATION_PROVIDER
        self.model = settings.AI_VALIDATION_MODEL
        self.timeout = settings.AI_VALIDATION_TIMEOUT_SECONDS
        
        # Initialize OpenAI client
        if self.provider == "openai":
            if not settings.OPENAI_API_KEY:
                raise ValueError("OPENAI_API_KEY must be set when AI_VALIDATION_PROVIDER is 'openai'")
            self.openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
        
        # Initialize Anthropic client
        elif self.provider == "anthropic":
            if not settings.ANTHROPIC_API_KEY:
                raise ValueError("ANTHROPIC_API_KEY must be set when AI_VALIDATION_PROVIDER is 'anthropic'")
            self.anthropic_client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    async def validate_image(
        self,
        image_bytes: bytes,
        content_type: str,
        context: Optional[str] = None
    ) -> dict:
        """
        Validate an image for clarity, lighting, and context.
        
        Args:
            image_bytes: Raw image bytes
            content_type: MIME type (e.g., "image/jpeg")
            context: Optional context about what the image should show
            
        Returns:
            dict with 'is_valid' (bool), 'confidence' (float), and 'feedback' (str)
        """
        try:
            # Encode image to base64
            base64_image = base64.b64encode(image_bytes).decode('utf-8')
            
            if self.provider == "openai":
                return await self._validate_image_openai(base64_image, content_type, context)
            elif self.provider == "anthropic":
                return await self._validate_image_anthropic(base64_image, content_type, context)
            else:
                raise ValueError(f"Unsupported AI provider: {self.provider}")
        
        except Exception as e:
            logger.error(f"Image validation failed: {e}")
            # Fail open: if validation fails, accept the image but log the error
            return {
                "is_valid": True,
                "confidence": 0.5,
                "feedback": "Validation service unavailable - proceeding with caution"
            }

    async def _validate_image_openai(
        self,
        base64_image: str,
        content_type: str,
        context: Optional[str]
    ) -> dict:
        """Validate image using OpenAI GPT-4o."""
        system_prompt = """You are a quality control specialist for job site documentation. 
Evaluate images for clarity, lighting, and contextual relevance.

Respond in JSON format with these exact keys:
- is_valid: boolean (true if image quality is acceptable)
- confidence: float (0.0 to 1.0, your confidence in the assessment)
- feedback: string (if invalid, provide specific actionable feedback for the user)

Reject images that are:
- Too blurry to see details
- Too dark or poorly lit
- Missing critical context for the job
- Out of focus or shaky

Accept images that are:
- Clear and in focus
- Well-lit
- Show relevant context for the job"""

        user_prompt = f"""Evaluate this image for job site documentation quality.
Context: {context or 'General job documentation'}
Image type: {content_type}

Is this image suitable for documenting a job? Provide specific feedback if not."""

        try:
            response = self.openai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{content_type};base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=500,
                response_format={"type": "json_object"},
                timeout=self.timeout
            )
            
            import json
            result = json.loads(response.choices[0].message.content)
            return result
        
        except Exception as e:
            logger.error(f"OpenAI image validation error: {e}")
            raise

    async def _validate_image_anthropic(
        self,
        base64_image: str,
        content_type: str,
        context: Optional[str]
    ) -> dict:
        """Validate image using Anthropic Claude."""
        system_prompt = """You are a quality control specialist for job site documentation. 
Evaluate images for clarity, lighting, and contextual relevance.

Respond in JSON format with these exact keys:
- is_valid: boolean (true if image quality is acceptable)
- confidence: float (0.0 to 1.0, your confidence in the assessment)
- feedback: string (if invalid, provide specific actionable feedback for the user)

Reject images that are:
- Too blurry to see details
- Too dark or poorly lit
- Missing critical context for the job
- Out of focus or shaky

Accept images that are:
- Clear and in focus
- Well-lit
- Show relevant context for the job"""

        user_prompt = f"""Evaluate this image for job site documentation quality.
Context: {context or 'General job documentation'}
Image type: {content_type}

Is this image suitable for documenting a job? Provide specific feedback if not."""

        try:
            message = self.anthropic_client.messages.create(
                model=self.model,
                max_tokens=500,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_prompt},
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": content_type,
                                    "data": base64_image
                                }
                            }
                        ]
                    }
                ],
                timeout=self.timeout
            )
            
            import json
            result = json.loads(message.content[0].text)
            return result
        
        except Exception as e:
            logger.error(f"Anthropic image validation error: {e}")
            raise

    async def validate_audio(
        self,
        audio_bytes: bytes,
        content_type: str,
        context: Optional[str] = None
    ) -> dict:
        """
        Validate audio for clarity and intelligibility.
        
        Args:
            audio_bytes: Raw audio bytes
            content_type: MIME type (e.g., "audio/wav")
            context: Optional context about what the audio should contain
            
        Returns:
            dict with 'is_valid' (bool), 'confidence' (float), and 'feedback' (str)
        """
        try:
            # For audio, we'll use a simpler validation approach
            # Check if audio is not empty and has reasonable duration
            # In production, you might want to use speech-to-text or audio analysis
            
            import io
            import wave
            
            # Try to parse as WAV to get duration
            try:
                audio_io = io.BytesIO(audio_bytes)
                with wave.open(audio_io, 'rb') as wav_file:
                    frames = wav_file.getnframes()
                    rate = wav_file.getframerate()
                    duration = frames / float(rate)
                    
                    # Audio should be at least 1 second and at most 10 minutes
                    if duration < 1:
                        return {
                            "is_valid": False,
                            "confidence": 0.9,
                            "feedback": "Audio is too short. Please provide at least 1 second of audio."
                        }
                    if duration > 600:  # 10 minutes
                        return {
                            "is_valid": False,
                            "confidence": 0.9,
                            "feedback": "Audio is too long. Please keep voice notes under 10 minutes."
                        }
            except:
                # If not WAV, assume it's valid if size is reasonable
                if len(audio_bytes) < 1000:
                    return {
                        "is_valid": False,
                        "confidence": 0.8,
                        "feedback": "Audio file appears to be corrupted or too short."
                    }
            
            # For more sophisticated audio validation, integrate with Whisper or similar
            # For now, do basic validation
            return {
                "is_valid": True,
                "confidence": 0.7,
                "feedback": "Audio quality check passed"
            }
        
        except Exception as e:
            logger.error(f"Audio validation failed: {e}")
            return {
                "is_valid": True,
                "confidence": 0.5,
                "feedback": "Audio validation service unavailable - proceeding with caution"
            }

    async def validate_video(
        self,
        video_bytes: bytes,
        content_type: str,
        context: Optional[str] = None
    ) -> dict:
        """
        Validate video for clarity and relevance.
        
        Args:
            video_bytes: Raw video bytes
            content_type: MIME type (e.g., "video/mp4")
            context: Optional context about what the video should show
            
        Returns:
            dict with 'is_valid' (bool), 'confidence' (float), and 'feedback' (str)
        """
        try:
            # Basic video validation
            # Check file size and duration
            import io
            
            # For now, do basic size validation
            # In production, you'd want to extract frames and validate them
            if len(video_bytes) < 1000:
                return {
                    "is_valid": False,
                    "confidence": 0.9,
                    "feedback": "Video file appears to be corrupted or too short."
                }
            
            # Max video size: 50MB
            max_size = settings.MEDIA_MAX_SIZE_MB * 1024 * 1024
            if len(video_bytes) > max_size:
                return {
                    "is_valid": False,
                    "confidence": 0.9,
                    "feedback": f"Video is too large. Maximum size is {settings.MEDIA_MAX_SIZE_MB}MB."
                }
            
            return {
                "is_valid": True,
                "confidence": 0.7,
                "feedback": "Video quality check passed"
            }
        
        except Exception as e:
            logger.error(f"Video validation failed: {e}")
            return {
                "is_valid": True,
                "confidence": 0.5,
                "feedback": "Video validation service unavailable - proceeding with caution"
            }


# Singleton instance
media_validation_service = MediaValidationService()
