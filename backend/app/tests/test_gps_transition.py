from decimal import Decimal
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.api.v1.endpoints.booking import LocationUpdate
from app.models.booking import Booking, BookingStatus


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def mock_booking():
    booking = MagicMock(spec=Booking)
    booking.id = uuid4()
    booking.artisan_id = 1
    booking.location = "123 Main St"
    booking.status = BookingStatus.CONFIRMED
    return booking


@pytest.fixture
def mock_artisan():
    artisan = MagicMock()
    artisan.id = 1
    artisan.user_id = 1
    return artisan


@pytest.fixture
def mock_user():
    user = MagicMock()
    user.id = 1
    user.role = "artisan"
    return user


@patch("app.services.geolocation.geolocation_service.geocode_address")
@patch("app.services.geolocation.geolocation_service.calculate_distance")
@patch("app.services.soroban.transition_to_in_progress")
@pytest.mark.asyncio
async def test_update_location_verified_arrival(
    mock_soroban,
    mock_calc_dist,
    mock_geocode,
    mock_db,
    mock_booking,
    mock_artisan,
    mock_user,
):
    # Setup mocks
    mock_geocode.return_value = MagicMock(
        latitude=Decimal("10.0"), longitude=Decimal("20.0")
    )
    mock_calc_dist.return_value = 0.05  # 50m (within 100m)

    # Mock DB queries
    mock_db.query().filter().first.side_effect = [mock_booking, mock_artisan]

    from app.api.v1.endpoints.booking import update_location

    location_data = LocationUpdate(latitude=10.0001, longitude=20.0001)

    result = await update_location(
        booking_id=mock_booking.id,
        location_data=location_data,
        db=mock_db,
        current_user=mock_user,
    )

    assert result["status"] == "arrived"
    assert result["distance_km"] == 0.05
    mock_soroban.assert_called_once()
    assert mock_booking.status == BookingStatus.IN_PROGRESS


@patch("app.services.geolocation.geolocation_service.geocode_address")
@patch("app.services.geolocation.geolocation_service.calculate_distance")
@patch("app.services.soroban.transition_to_in_progress")
@pytest.mark.asyncio
async def test_update_location_in_transit(
    mock_soroban,
    mock_calc_dist,
    mock_geocode,
    mock_db,
    mock_booking,
    mock_artisan,
    mock_user,
):
    # Setup mocks
    mock_geocode.return_value = MagicMock(
        latitude=Decimal("10.0"), longitude=Decimal("20.0")
    )
    mock_calc_dist.return_value = 0.5  # 500m (outside 100m)

    # Mock DB queries
    mock_db.query().filter().first.side_effect = [mock_booking, mock_artisan]

    from app.api.v1.endpoints.booking import update_location

    location_data = LocationUpdate(latitude=10.01, longitude=20.01)

    result = await update_location(
        booking_id=mock_booking.id,
        location_data=location_data,
        db=mock_db,
        current_user=mock_user,
    )

    assert result["status"] == "in_transit"
    assert result["distance_km"] == 0.5
    mock_soroban.assert_not_called()
    assert mock_booking.status == BookingStatus.CONFIRMED
