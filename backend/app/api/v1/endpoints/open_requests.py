import math
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.auth import require_client
from app.db.session import get_db
from app.models.open_request import OpenRequest, OpenRequestStatus
from app.models.user import User
from app.schemas.open_request import (
    OpenRequestCreate,
    OpenRequestListResponse,
    OpenRequestResponse,
    OpenRequestUpdate,
)

router = APIRouter()


def _haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate the great-circle distance between two points in kilometers."""
    R = 6371  # Earth's radius in km

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlng / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


@router.post(
    "",
    response_model=OpenRequestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new open request",
)
def create_open_request(
    request_data: OpenRequestCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_client),
):
    """
    Create a new open request. Only clients can create open requests.
    """
    # Get or create client profile
    from app.models.client import Client

    client_profile = db.query(Client).filter(Client.user_id == current_user.id).first()
    if not client_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Client profile not found. Please create a client profile first.",
        )

    open_request = OpenRequest(
        client_id=client_profile.id,
        title=request_data.title,
        description=request_data.description,
        budget=request_data.budget,
        location_lat=request_data.location_lat,
        location_lng=request_data.location_lng,
    )

    db.add(open_request)
    db.commit()
    db.refresh(open_request)

    return open_request


@router.get(
    "",
    response_model=OpenRequestListResponse,
    summary="List open requests with optional location filtering",
)
def list_open_requests(
    lat: float
    | None = Query(None, ge=-90, le=90, description="Latitude for location filtering"),
    lng: float
    | None = Query(
        None, ge=-180, le=180, description="Longitude for location filtering"
    ),
    radius_km: float = Query(50, gt=0, description="Search radius in kilometers"),
    status_filter: str
    | None = Query(None, alias="status", description="Filter by status"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of records"),
    db: Session = Depends(get_db),
):
    """
    List open requests with optional location-based filtering.
    If lat/lng are provided, only requests within radius_km are returned.
    """
    query = db.query(OpenRequest)

    # Apply status filter
    if status_filter:
        try:
            status_enum = OpenRequestStatus(status_filter)
            query = query.filter(OpenRequest.status == status_enum)
        except ValueError:
            valid_values = [s.value for s in OpenRequestStatus]
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status_filter}. Valid values: {valid_values}",
            ) from None
    else:
        # Default to only OPEN requests
        query = query.filter(OpenRequest.status == OpenRequestStatus.OPEN)

    # Apply location filter if coordinates provided
    if lat is not None and lng is not None:
        results = query.all()
        # Filter by distance in Python (could be optimized with PostGIS)
        filtered_results = []
        for req in results:
            if req.location_lat is not None and req.location_lng is not None:
                distance = _haversine_distance(
                    lat, lng, float(req.location_lat), float(req.location_lng)
                )
                if distance <= radius_km:
                    filtered_results.append(req)
            else:
                # Include requests without location if no location filter
                filtered_results.append(req)

        # Apply pagination
        total = len(filtered_results)
        paginated = filtered_results[skip : skip + limit]

        return OpenRequestListResponse(
            items=[OpenRequestResponse.model_validate(r) for r in paginated],
            total=total,
        )

    # Apply pagination for non-location queries
    total = query.count()
    results = query.offset(skip).limit(limit).all()

    return OpenRequestListResponse(
        items=[OpenRequestResponse.model_validate(r) for r in results],
        total=total,
    )


@router.get(
    "/{request_id}",
    response_model=OpenRequestResponse,
    summary="Get a specific open request",
)
def get_open_request(
    request_id: UUID,
    db: Session = Depends(get_db),
):
    """
    Get a specific open request by ID.
    """
    open_request = db.query(OpenRequest).filter(OpenRequest.id == request_id).first()
    if not open_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Open request not found",
        )

    return open_request


@router.put(
    "/{request_id}",
    response_model=OpenRequestResponse,
    summary="Update an open request",
)
def update_open_request(
    request_id: UUID,
    request_data: OpenRequestUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_client),
):
    """
    Update an open request. Only the owner can update their request.
    """
    from app.models.client import Client

    client_profile = db.query(Client).filter(Client.user_id == current_user.id).first()
    if not client_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Client profile not found.",
        )

    open_request = (
        db.query(OpenRequest)
        .filter(
            OpenRequest.id == request_id,
            OpenRequest.client_id == client_profile.id,
        )
        .first()
    )

    if not open_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Open request not found or you don't have permission to modify it",
        )

    # Update fields
    update_data = request_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "status":
            try:
                value = OpenRequestStatus(value)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status: {value}",
                ) from None
        setattr(open_request, field, value)

    db.commit()
    db.refresh(open_request)

    return open_request


@router.delete(
    "/{request_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an open request",
)
def delete_open_request(
    request_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_client),
):
    """
    Delete an open request. Only the owner can delete their request.
    """
    from app.models.client import Client

    client_profile = db.query(Client).filter(Client.user_id == current_user.id).first()
    if not client_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Client profile not found.",
        )

    open_request = (
        db.query(OpenRequest)
        .filter(
            OpenRequest.id == request_id,
            OpenRequest.client_id == client_profile.id,
        )
        .first()
    )

    if not open_request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Open request not found or you don't have permission to delete it",
        )

    db.delete(open_request)
    db.commit()

    return None
