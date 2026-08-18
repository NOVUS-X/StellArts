import asyncio
import logging
import random
import uuid
from typing import Optional

from app.core.config import settings
from app.core.exceptions import LLMServiceError, LLMRateLimitError
from app.services.llm.base_provider import BaseLLMProvider, SpecialtyExtractionResult, PriceEstimateResult
from app.services.llm.openai_provider import OpenAIProvider
from app.services.llm.gemini_provider import GeminiProvider

logger = logging.getLogger(__name__)


class LLMService:
    """
    Unified LLM service with provider abstraction and retry logic
    """
    
    def __init__(self):
        self.provider: Optional[BaseLLMProvider] = None
        self._initialize_provider()
    
    def _initialize_provider(self):
        """Initialize LLM provider based on configuration"""
        provider_name = settings.LLM_PROVIDER.lower()
        
        if provider_name == "openai":
            if not settings.OPENAI_API_KEY:
                raise ValueError("OPENAI_API_KEY not configured")
            self.provider = OpenAIProvider()
            logger.info("Initialized OpenAI provider")
        elif provider_name == "gemini":
            if not settings.GEMINI_API_KEY:
                raise ValueError("GEMINI_API_KEY not configured")
            self.provider = GeminiProvider()
            logger.info("Initialized Gemini provider")
        else:
            raise ValueError(f"Unsupported LLM provider: {provider_name}")
    
    async def extract_specialties_with_retry(
        self,
        job_description: str,
        taxonomy: list[str],
        max_retries: int = 3
    ) -> SpecialtyExtractionResult:
        """
        Extract specialties with exponential backoff retry
        """
        request_id = self._generate_request_id()
        start_time = asyncio.get_event_loop().time()
        
        logger.info(
            f"LLM Request [{request_id}]: Extracting specialties",
            extra={
                "request_id": request_id,
                "description_length": len(job_description),
                "provider": settings.LLM_PROVIDER
            }
        )
        
        for attempt in range(max_retries):
            try:
                result = await self.provider.extract_specialties(
                    job_description, 
                    taxonomy
                )
                
                duration = asyncio.get_event_loop().time() - start_time
                logger.info(
                    f"LLM Response [{request_id}]: Success",
                    extra={
                        "request_id": request_id,
                        "specialties": result.specialties,
                        "duration_seconds": round(duration, 3),
                        "attempt": attempt + 1
                    }
                )
                
                return result
                
            except Exception as e:
                is_rate_limit = self._is_rate_limit_error(e)
                is_retryable = self._is_retryable_error(e)
                
                logger.warning(
                    f"LLM Request [{request_id}]: Error on attempt {attempt + 1}",
                    extra={
                        "request_id": request_id,
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "is_rate_limit": is_rate_limit,
                        "is_retryable": is_retryable
                    }
                )
                
                if attempt < max_retries - 1 and (is_rate_limit or is_retryable):
                    backoff_time = self._calculate_backoff(attempt, is_rate_limit)
                    logger.info(f"Retrying in {backoff_time:.2f} seconds...")
                    await asyncio.sleep(backoff_time)
                else:
                    logger.error(
                        f"LLM Request [{request_id}]: All retries exhausted",
                        extra={"request_id": request_id, "final_error": str(e)}
                    )
                    raise LLMServiceError(
                        f"Failed to extract specialties after {max_retries} attempts: {str(e)}"
                    )
    
    async def estimate_price_with_retry(
        self,
        job_description: str,
        location: str,
        specialty_tags: list[str],
        max_retries: int = 3
    ) -> PriceEstimateResult:
        """
        Estimate price with exponential backoff retry
        """
        request_id = self._generate_request_id()
        start_time = asyncio.get_event_loop().time()
        
        logger.info(
            f"LLM Request [{request_id}]: Estimating price",
            extra={
                "request_id": request_id,
                "location": location,
                "specialties": specialty_tags,
                "provider": settings.LLM_PROVIDER
            }
        )
        
        for attempt in range(max_retries):
            try:
                result = await self.provider.estimate_price(
                    job_description,
                    location,
                    specialty_tags
                )
                
                duration = asyncio.get_event_loop().time() - start_time
                logger.info(
                    f"LLM Response [{request_id}]: Success",
                    extra={
                        "request_id": request_id,
                        "min_price": result.min_price,
                        "max_price": result.max_price,
                        "duration_seconds": round(duration, 3),
                        "attempt": attempt + 1
                    }
                )
                
                return result
                
            except Exception as e:
                is_rate_limit = self._is_rate_limit_error(e)
                is_retryable = self._is_retryable_error(e)
                
                logger.warning(
                    f"LLM Request [{request_id}]: Error on attempt {attempt + 1}",
                    extra={
                        "request_id": request_id,
                        "error_type": type(e).__name__,
                        "error_message": str(e),
                        "is_rate_limit": is_rate_limit,
                        "is_retryable": is_retryable
                    }
                )
                
                if attempt < max_retries - 1 and (is_rate_limit or is_retryable):
                    backoff_time = self._calculate_backoff(attempt, is_rate_limit)
                    logger.info(f"Retrying in {backoff_time:.2f} seconds...")
                    await asyncio.sleep(backoff_time)
                else:
                    logger.error(
                        f"LLM Request [{request_id}]: All retries exhausted",
                        extra={"request_id": request_id, "final_error": str(e)}
                    )
                    raise LLMRateLimitError(
                        f"Failed to estimate price after {max_retries} attempts: {str(e)}"
                    )
    
    def _is_rate_limit_error(self, error: Exception) -> bool:
        """Check if error is a rate limit error (429)"""
        error_str = str(error).lower()
        error_type = type(error).__name__
        return (
            "429" in error_str or
            "rate limit" in error_str or
            "quota" in error_str or
            "resource_exhausted" in error_str or
            error_type in ["RateLimitError", "ResourceExhausted"]
        )
    
    def _is_retryable_error(self, error: Exception) -> bool:
        """Check if error is retryable (5xx, timeouts, network errors)"""
        error_str = str(error).lower()
        error_type = type(error).__name__
        return (
            "500" in error_str or
            "502" in error_str or
            "503" in error_str or
            "504" in error_str or
            "timeout" in error_str or
            "connection" in error_str or
            error_type in ["APITimeoutError", "APIConnectionError", "InternalServerError"]
        )
    
    def _calculate_backoff(self, attempt: int, is_rate_limit: bool) -> float:
        """
        Calculate exponential backoff with jitter
        
        For rate limits: 1s, 2s, 4s base with jitter
        For other errors: 0.5s, 1s, 2s base with jitter
        """
        if is_rate_limit:
            base_delay = 2 ** attempt  # 1, 2, 4, 8...
        else:
            base_delay = 0.5 * (2 ** attempt)  # 0.5, 1, 2, 4...
        
        # Add jitter: ±25% randomization
        jitter = base_delay * 0.25 * (2 * random.random() - 1)
        total_delay = base_delay + jitter
        
        # Cap at 60 seconds
        return min(total_delay, 60.0)
    
    def _generate_request_id(self) -> str:
        """Generate unique request ID for logging"""
        return str(uuid.uuid4())[:8]
    
    async def health_check(self) -> dict:
        """Check LLM provider health"""
        is_healthy = await self.provider.health_check()
        return {
            "provider": settings.LLM_PROVIDER,
            "healthy": is_healthy
        }


# Global instance
llm_service = LLMService()
