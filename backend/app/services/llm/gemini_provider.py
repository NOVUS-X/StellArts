import json
import logging
import google.generativeai as genai

from app.core.config import settings
from .base_provider import BaseLLMProvider, SpecialtyExtractionResult, PriceEstimateResult

logger = logging.getLogger(__name__)


class GeminiProvider(BaseLLMProvider):
    """Google Gemini implementation"""
    
    def __init__(self):
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel(
            settings.GEMINI_MODEL or "gemini-1.5-flash",
            generation_config={
                "temperature": 0.3,
                "response_mime_type": "application/json"
            }
        )
    
    async def extract_specialties(
        self, 
        job_description: str,
        taxonomy: list[str]
    ) -> SpecialtyExtractionResult:
        """Extract specialty tags using Gemini"""
        
        prompt = f"""You are a job classification expert for a home services marketplace.
Analyze the job description and extract 1-5 relevant specialty tags from this taxonomy:
{', '.join(taxonomy)}

Return a JSON object with this exact structure:
{{
    "specialties": ["specialty1", "specialty2"],
    "confidence_scores": {{"specialty1": 0.95, "specialty2": 0.80}},
    "requires_clarification": false,
    "clarification_questions": []
}}

If the description is ambiguous, set requires_clarification to true and provide questions.

Job description: {job_description}"""

        response = await self.model.generate_content_async(prompt)
        result_json = json.loads(response.text)
        return SpecialtyExtractionResult(**result_json)
    
    async def estimate_price(
        self,
        job_description: str,
        location: str,
        specialty_tags: list[str]
    ) -> PriceEstimateResult:
        """Generate price estimate using Gemini"""
        
        prompt = f"""You are a pricing expert for home services.
Provide a realistic price estimate for this job.

Location: {location}
Specialties: {', '.join(specialty_tags)}
Job description: {job_description}

Return a JSON object with this exact structure:
{{
    "min_price": 150.00,
    "max_price": 300.00,
    "confidence": 0.85,
    "reasoning": "Brief explanation of pricing factors"
}}

Consider typical labor rates, material costs, time requirements, and local market rates."""

        response = await self.model.generate_content_async(prompt)
        result_json = json.loads(response.text)
        return PriceEstimateResult(**result_json)
    
    async def health_check(self) -> bool:
        """Check Gemini API availability"""
        try:
            await self.model.generate_content_async("test")
            return True
        except Exception as e:
            logger.error(f"Gemini health check failed: {e}")
            return False
