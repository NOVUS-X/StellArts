from abc import ABC, abstractmethod
from pydantic import BaseModel


class SpecialtyExtractionResult(BaseModel):
    """Structured output for specialty extraction"""
    specialties: list[str]
    confidence_scores: dict[str, float]
    requires_clarification: bool = False
    clarification_questions: list[str] = []


class PriceEstimateResult(BaseModel):
    """Structured output for price estimation"""
    min_price: float
    max_price: float
    currency: str = "USD"
    confidence: float
    reasoning: str


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers"""
    
    @abstractmethod
    async def extract_specialties(
        self, 
        job_description: str,
        taxonomy: list[str]
    ) -> SpecialtyExtractionResult:
        """Extract specialty tags from job description"""
        pass
    
    @abstractmethod
    async def estimate_price(
        self,
        job_description: str,
        location: str,
        specialty_tags: list[str]
    ) -> PriceEstimateResult:
        """Generate price estimate for job"""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if provider is available"""
        pass
