import json
import logging
from openai import AsyncOpenAI

from app.core.config import settings
from .base_provider import BaseLLMProvider, SpecialtyExtractionResult, PriceEstimateResult

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseLLMProvider):
    """OpenAI GPT implementation"""
    
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            max_retries=0,  # We handle retries in LLMService
            timeout=10.0
        )
        self.model = settings.OPENAI_MODEL or "gpt-4o-mini"
    
    async def extract_specialties(
        self, 
        job_description: str,
        taxonomy: list[str]
    ) -> SpecialtyExtractionResult:
        """Extract specialty tags using structured outputs"""
        
        response_schema = {
            "type": "object",
            "properties": {
                "specialties": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of specialty tags from the taxonomy"
                },
                "confidence_scores": {
                    "type": "object",
                    "description": "Confidence score (0-1) for each specialty"
                },
                "requires_clarification": {
                    "type": "boolean",
                    "description": "True if description is ambiguous"
                },
                "clarification_questions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Questions to ask for clarification"
                }
            },
            "required": ["specialties", "confidence_scores"],
            "additionalProperties": False
        }
        
        system_prompt = f"""You are a job classification expert for a home services marketplace.
Analyze the job description and extract 1-5 relevant specialty tags from this taxonomy:
{', '.join(taxonomy)}

If the description is ambiguous or lacks detail, set requires_clarification to true and suggest questions.
For each specialty, provide a confidence score between 0 and 1."""

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": job_description}
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "specialty_extraction",
                    "schema": response_schema,
                    "strict": True
                }
            },
            temperature=0.3,
            max_tokens=500
        )
        
        result_json = json.loads(response.choices[0].message.content)
        return SpecialtyExtractionResult(**result_json)
    
    async def estimate_price(
        self,
        job_description: str,
        location: str,
        specialty_tags: list[str]
    ) -> PriceEstimateResult:
        """Generate price estimate using structured outputs"""
        
        response_schema = {
            "type": "object",
            "properties": {
                "min_price": {
                    "type": "number",
                    "description": "Minimum estimated price in USD"
                },
                "max_price": {
                    "type": "number",
                    "description": "Maximum estimated price in USD"
                },
                "confidence": {
                    "type": "number",
                    "description": "Confidence in estimate (0-1)"
                },
                "reasoning": {
                    "type": "string",
                    "description": "Brief explanation of pricing factors"
                }
            },
            "required": ["min_price", "max_price", "confidence", "reasoning"],
            "additionalProperties": False
        }
        
        system_prompt = f"""You are a pricing expert for home services.
Provide a realistic price estimate for this job based on:
- Job description and scope
- Location: {location}
- Specialties: {', '.join(specialty_tags)}
- Typical labor rates, material costs, and time requirements

Consider local market rates and job complexity. Provide minimum and maximum estimates in USD."""

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": job_description}
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "price_estimate",
                    "schema": response_schema,
                    "strict": True
                }
            },
            temperature=0.5,
            max_tokens=300
        )
        
        result_json = json.loads(response.choices[0].message.content)
        return PriceEstimateResult(**result_json)
    
    async def health_check(self) -> bool:
        """Check OpenAI API availability"""
        try:
            await self.client.models.list()
            return True
        except Exception as e:
            logger.error(f"OpenAI health check failed: {e}")
            return False
