import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.auth import require_client, get_current_active_user
from app.db.session import get_db
from app.models.booking import Booking, BookingStatus
from app.models.client import Client
from app.models.user import User
from app.services.job_matcher import job_matcher
from app.services.price_estimator import price_estimator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["jobs"])


class JobCreateRequest(BaseModel):
    """Request model for creating a new job with AI processing"""
    description: str = Field(..., min_length=10, max_length=2000)
    location: str = Field(..., min_length=3)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    estimated_hours: Optional[float] = Field(None, gt=0)
    date: Optional[datetime] = None


class JobCreateResponse(BaseModel):
    """Response model with AI matching results"""
    job_id: str
    specialty_tags: list[str]
    matched_artisans: list[dict]
    price_estimate: dict
    requires_clarification: bool
    clarification_questions: list[str]


@router.post("/create", response_model=JobCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_job_with_ai_matching(
    job_data: JobCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_client)
):
    """
    Create a new job with AI-powered specialty extraction, artisan matching, and price estimation
    
    Process:
    1. Extract specialty tags from job description using LLM
    2. Match with qualified artisans within 10km radius
    3. Generate price estimate
    4. Dispatch notifications to top 5 matched artisans
    5. Store job with AI metadata
    """
    try:
        # Step 1 & 2: AI matching and specialty extraction
        matching_result = await job_matcher.process_job_description(
            db=db,
            job_description=job_data.description,
            job_location=job_data.location,
            job_latitude=Decimal(str(job_data.latitude)) if job_data.latitude else None,
            job_longitude=Decimal(str(job_data.longitude)) if job_data.longitude else None
        )
        
        if matching_result.get("error"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=matching_result["error"]
            )
        
        # Step 3: Generate price estimate
        price_estimate_result = await price_estimator.estimate_job_price(
            db=db,
            job_description=job_data.description,
            location=job_data.location,
            specialty_tags=matching_result["specialty_tags"]
        )
        
        # Step 4: Create job record
        client = db.query(Client).filter(Client.user_id == current_user.id).first()
        if not client:
            client = Client(user_id=current_user.id)
            db.add(client)
            db.flush()
        
        # Create job as booking with pending artisan assignment
        new_job = Booking(
            client_id=client.id,
            artisan_id=None,  # Will be assigned when artisan accepts
            service=job_data.description,
            estimated_hours=job_data.estimated_hours,
            location=job_data.location,
            date=job_data.date,
            status=BookingStatus.PENDING,
            specialty_tags=matching_result["specialty_tags"],
            matched_artisan_ids=[a["artisan_id"] for a in matching_result["matched_artisans"]],
            ai_estimate_min=Decimal(str(price_estimate_result["min_price"])) if price_estimate_result["min_price"] else None,
            ai_estimate_max=Decimal(str(price_estimate_result["max_price"])) if price_estimate_result["max_price"] else None,
            ai_estimate_confidence=Decimal(str(price_estimate_result["confidence"])),
            ai_estimate_method=price_estimate_result["method"]
        )
        
        db.add(new_job)
        db.commit()
        db.refresh(new_job)
        
        return JobCreateResponse(
            job_id=str(new_job.id),
            specialty_tags=matching_result["specialty_tags"],
            matched_artisans=matching_result["matched_artisans"],
            price_estimate=price_estimate_result,
            requires_clarification=matching_result["requires_clarification"],
            clarification_questions=matching_result.get("clarification_questions", [])
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating job with AI matching: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing your job request. Please try again."
        )


@router.get("/{job_id}/estimate")
async def get_job_price_estimate(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Get AI-generated price estimate for an existing job
    """
    try:
        job = db.query(Booking).filter(Booking.id == UUID(job_id)).first()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid job ID format")
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Check if estimate already exists
    if job.ai_estimate_min and job.ai_estimate_max:
        return {
            "min_price": float(job.ai_estimate_min),
            "max_price": float(job.ai_estimate_max),
            "confidence": float(job.ai_estimate_confidence) if job.ai_estimate_confidence else 0.0,
            "method": job.ai_estimate_method,
            "cached": True
        }
    
    # Generate new estimate
    specialty_tags = job.specialty_tags if job.specialty_tags else []
    
    if not specialty_tags:
        # Extract specialties first
        matching_result = await job_matcher.process_job_description(
            db=db,
            job_description=job.service,
            job_location=job.location
        )
        specialty_tags = matching_result["specialty_tags"]
    
    estimate = await price_estimator.estimate_job_price(
        db=db,
        job_description=job.service,
        location=job.location,
        specialty_tags=specialty_tags
    )
    
    # Update job with estimate
    if estimate["min_price"]:
        job.ai_estimate_min = Decimal(str(estimate["min_price"]))
        job.ai_estimate_max = Decimal(str(estimate["max_price"]))
        job.ai_estimate_confidence = Decimal(str(estimate["confidence"]))
        job.ai_estimate_method = estimate["method"]
        db.commit()
    
    return {**estimate, "cached": False}
