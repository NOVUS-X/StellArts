import asyncio
import json
import logging
from decimal import Decimal
from typing import Optional

from sqlalchemy import and_
from sqlalchemy.orm import Session
from fuzzywuzzy import fuzz

from app.core.config import settings
from app.models.artisan import Artisan
from app.services.geolocation import geolocation_service
from app.services.llm_service import llm_service
from app.services.notification_service import create_notification

logger = logging.getLogger(__name__)


class JobMatcherService:
    """
    Service for matching jobs to qualified artisans
    """
    
    def __init__(self):
        # System taxonomy of valid specialty tags
        self.specialty_taxonomy = [
            "Plumbing",
            "Electrical",
            "HVAC",
            "Carpentry",
            "Painting",
            "Roofing",
            "Flooring",
            "Landscaping",
            "Cleaning",
            "Appliance Repair",
            "Handyman",
            "Pest Control",
            "Masonry",
            "Welding",
            "Drywall",
            "Tiling",
            "Locksmith",
            "Window Installation",
            "Fence Installation",
            "Garage Door Repair"
        ]
        self.confidence_threshold = settings.SPECIALTY_CONFIDENCE_THRESHOLD
        self.proximity_radius_km = settings.JOB_MATCHING_PROXIMITY_KM
        self.max_matched_artisans = settings.JOB_MATCHING_MAX_ARTISANS
    
    async def process_job_description(
        self,
        db: Session,
        job_description: str,
        job_location: str,
        job_latitude: Optional[Decimal] = None,
        job_longitude: Optional[Decimal] = None
    ) -> dict:
        """
        Process natural language job description and match with artisans
        
        Returns:
            dict with keys: specialty_tags, matched_artisans, requires_clarification
        """
        start_time = asyncio.get_event_loop().time()
        
        # Step 1: Extract specialty tags from LLM
        logger.info(f"Extracting specialties from job description: {job_description[:50]}...")
        
        extraction_result = await llm_service.extract_specialties_with_retry(
            job_description,
            self.specialty_taxonomy
        )
        
        # Step 2: Map to system taxonomy with fuzzy matching
        validated_tags = self._validate_and_map_specialties(
            extraction_result.specialties,
            extraction_result.confidence_scores
        )
        
        if not validated_tags:
            logger.warning("No valid specialty tags extracted from job description")
            return {
                "specialty_tags": [],
                "matched_artisans": [],
                "requires_clarification": True,
                "clarification_questions": extraction_result.clarification_questions or [
                    "Could you provide more details about the type of work needed?"
                ]
            }
        
        logger.info(f"Validated specialty tags: {validated_tags}")
        
        # Step 3: Geocode job location if coordinates not provided
        if job_latitude is None or job_longitude is None:
            geo_result = await geolocation_service.geocode_address(job_location)
            if geo_result:
                job_latitude = geo_result.latitude
                job_longitude = geo_result.longitude
            else:
                logger.error(f"Failed to geocode job location: {job_location}")
                return {
                    "specialty_tags": validated_tags,
                    "matched_artisans": [],
                    "requires_clarification": False,
                    "error": "Could not determine job location coordinates"
                }
        
        # Step 4: Find qualified artisans
        matched_artisans = await self._find_qualified_artisans(
            db,
            validated_tags,
            job_latitude,
            job_longitude
        )
        
        # Step 5: Dispatch notifications to top artisans
        if matched_artisans:
            await self._dispatch_notifications(
                db,
                matched_artisans,
                job_description,
                job_location
            )
        
        duration = asyncio.get_event_loop().time() - start_time
        logger.info(
            f"Job matching completed in {duration:.2f}s: "
            f"{len(matched_artisans)} artisans matched"
        )
        
        return {
            "specialty_tags": validated_tags,
            "matched_artisans": [
                {
                    "artisan_id": a.id,
                    "business_name": a.business_name,
                    "rating": float(a.rating) if a.rating else 0.0,
                    "distance_km": a.distance_km
                }
                for a in matched_artisans
            ],
            "requires_clarification": extraction_result.requires_clarification,
            "clarification_questions": extraction_result.clarification_questions or []
        }
    
    def _validate_and_map_specialties(
        self,
        suggested_specialties: list[str],
        confidence_scores: dict[str, float]
    ) -> list[str]:
        """
        Validate extracted specialties against taxonomy using fuzzy matching
        
        Rejects specialties with confidence < 70% or no good taxonomy match
        """
        validated = []
        
        for specialty in suggested_specialties:
            confidence = confidence_scores.get(specialty, 0.0)
            
            if confidence < self.confidence_threshold:
                logger.info(
                    f"Rejecting specialty '{specialty}' due to low confidence: {confidence:.2f}"
                )
                continue
            
            # Exact match
            if specialty in self.specialty_taxonomy:
                validated.append(specialty)
                continue
            
            # Fuzzy match to handle variations
            best_match = None
            best_score = 0
            
            for taxonomy_item in self.specialty_taxonomy:
                score = fuzz.ratio(specialty.lower(), taxonomy_item.lower())
                if score > best_score:
                    best_score = score
                    best_match = taxonomy_item
            
            # Accept fuzzy match if similarity >= 80%
            if best_score >= 80:
                logger.info(
                    f"Fuzzy matched '{specialty}' to '{best_match}' (score: {best_score})"
                )
                validated.append(best_match)
            else:
                logger.warning(
                    f"Could not map specialty '{specialty}' to taxonomy (best match: '{best_match}', score: {best_score})"
                )
        
        # Limit to 5 tags maximum
        return validated[:5]
    
    async def _find_qualified_artisans(
        self,
        db: Session,
        specialty_tags: list[str],
        job_latitude: Decimal,
        job_longitude: Decimal
    ) -> list[Artisan]:
        """
        Query database for qualified artisans within proximity
        
        Returns top artisans sorted by rating
        """
        # Step 1: Find nearby artisans using Redis geospatial index
        nearby_artisan_ids = await geolocation_service.find_nearby_artisans(
            latitude=job_latitude,
            longitude=job_longitude,
            radius_km=self.proximity_radius_km,
            limit=50  # Get more than needed for filtering
        )
        
        if not nearby_artisan_ids:
            logger.info("No artisans found within proximity radius")
            return []
        
        artisan_ids = [item["artisan_id"] for item in nearby_artisan_ids]
        distance_map = {item["artisan_id"]: item["distance_km"] for item in nearby_artisan_ids}
        
        # Step 2: Query PostgreSQL for artisans with matching specialties
        artisans = []
        
        for artisan_id in artisan_ids:
            artisan = db.query(Artisan).filter(
                and_(
                    Artisan.id == artisan_id,
                    Artisan.is_available == True,
                    Artisan.user_id.isnot(None)  # Must have associated user account
                )
            ).first()
            
            if artisan and artisan.specialties:
                try:
                    artisan_specialties = json.loads(artisan.specialties)
                except (json.JSONDecodeError, TypeError):
                    # Handle case where specialties is not valid JSON
                    artisan_specialties = []
                
                # Check if any specialty matches
                if any(tag in artisan_specialties for tag in specialty_tags):
                    artisan.distance_km = distance_map[artisan_id]
                    artisans.append(artisan)
        
        # Step 3: Sort by rating (descending) and return top artisans
        artisans_sorted = sorted(
            artisans,
            key=lambda a: (float(a.rating) if a.rating else 0.0, -a.distance_km),
            reverse=True
        )
        
        return artisans_sorted[:self.max_matched_artisans]
    
    async def _dispatch_notifications(
        self,
        db: Session,
        matched_artisans: list[Artisan],
        job_description: str,
        job_location: str
    ) -> None:
        """
        Dispatch notifications to matched artisans
        """
        notification_tasks = []
        
        for artisan in matched_artisans:
            if artisan.user_id:
                task = create_notification(
                    db=db,
                    user_id=artisan.user_id,
                    type="job_match",
                    title="New Job Match",
                    message=f"A new job matching your skills is available in {job_location}: {job_description[:100]}",
                    reference_id=None  # Will be set to job ID when job is created
                )
                notification_tasks.append(task)
        
        # Dispatch all notifications concurrently
        try:
            await asyncio.gather(*notification_tasks, return_exceptions=True)
            logger.info(f"Dispatched notifications to {len(matched_artisans)} artisans")
        except Exception as e:
            logger.error(f"Error dispatching notifications: {e}")


# Global instance
job_matcher = JobMatcherService()
