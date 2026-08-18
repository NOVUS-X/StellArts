import logging
from sqlalchemy.orm import Session

from app.services.llm_service import llm_service
from app.services.historical_data_service import historical_data_service
from app.core.exceptions import LLMRateLimitError

logger = logging.getLogger(__name__)


class PriceEstimatorService:
    """
    Service for generating AI-powered price estimates with historical fallback
    """
    
    async def estimate_job_price(
        self,
        db: Session,
        job_description: str,
        location: str,
        specialty_tags: list[str]
    ) -> dict:
        """
        Generate price estimate using LLM, falling back to historical data if needed
        
        Returns:
            dict with keys: min_price, max_price, confidence, method, disclaimer
        """
        try:
            # Attempt LLM-based estimation
            result = await llm_service.estimate_price_with_retry(
                job_description=job_description,
                location=location,
                specialty_tags=specialty_tags,
                max_retries=3
            )
            
            # Validate estimate
            if not self._validate_estimate(result.min_price, result.max_price):
                logger.warning(
                    f"Invalid LLM estimate: min={result.min_price}, max={result.max_price}"
                )
                raise ValueError("Invalid price range from LLM")
            
            logger.info(
                f"LLM price estimate: ${result.min_price:.2f} - ${result.max_price:.2f} "
                f"(confidence: {result.confidence:.2f})"
            )
            
            return {
                "min_price": float(result.min_price),
                "max_price": float(result.max_price),
                "confidence": result.confidence,
                "method": "llm",
                "reasoning": result.reasoning,
                "disclaimer": "This estimate is AI-generated and may vary from actual costs. Final pricing will be determined by the artisan."
            }
            
        except (LLMRateLimitError, Exception) as e:
            logger.warning(f"LLM estimation failed: {e}. Falling back to historical data.")
            
            # Fallback to historical data
            historical_estimate = await historical_data_service.get_historical_estimate(
                db=db,
                specialty_tags=specialty_tags,
                location=location
            )
            
            if historical_estimate:
                return {
                    "min_price": historical_estimate["min_price"],
                    "max_price": historical_estimate["max_price"],
                    "confidence": historical_estimate["confidence"],
                    "method": "historical",
                    "reasoning": historical_estimate["reasoning"],
                    "disclaimer": "This estimate is based on historical data and may vary from actual costs. Final pricing will be determined by the artisan."
                }
            else:
                # No historical data available
                logger.error("Both LLM and historical estimation failed")
                return {
                    "min_price": None,
                    "max_price": None,
                    "confidence": 0.0,
                    "method": "none",
                    "reasoning": "Unable to generate estimate due to insufficient data",
                    "disclaimer": "Pricing will be determined by the artisan after reviewing your request."
                }
    
    def _validate_estimate(self, min_price: float, max_price: float) -> bool:
        """
        Validate price estimate values
        
        Rules:
        - Both values must be positive
        - min_price <= max_price
        - max_price <= $10,000 (sanity check)
        - max_price <= 3 * min_price (prevent unrealistic ranges)
        """
        if min_price <= 0 or max_price <= 0:
            return False
        
        if min_price > max_price:
            return False
        
        if max_price > 10000:
            return False
        
        if max_price > 3 * min_price:
            logger.warning(f"Price range too wide: ${min_price} - ${max_price}")
            return False
        
        return True


# Global instance
price_estimator = PriceEstimatorService()
