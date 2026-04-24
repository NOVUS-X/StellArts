"""Test review creation and on-chain integration"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models.booking import Booking, BookingStatus
from app.models.client import Client
from app.models.user import User
from app.models.review import Review


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_headers(test_db: Session):
    """Create a test user and return auth headers"""
    # Create user
    user = User(
        email="review_test@test.com",
        username="review_tester",
        hashed_password="hashed_pass",
        role="client",
    )
    test_db.add(user)
    test_db.flush()

    # Create client profile
    client_profile = Client(user_id=user.id)
    test_db.add(client_profile)
    test_db.commit()

    return {"Authorization": f"Bearer test_token_{user.id}"}


@pytest.fixture
def test_booking(test_db: Session):
    """Create a test completed booking"""
    # Create artisan
    from app.models.artisan import Artisan
    
    artisan_user = User(
        email="artisan_review@test.com",
        username="test_artisan",
        hashed_password="hashed_pass",
        role="artisan",
    )
    test_db.add(artisan_user)
    test_db.flush()

    artisan = Artisan(user_id=artisan_user.id, stellar_address="GAAAA123TEST")
    test_db.add(artisan)
    test_db.flush()

    # Create client
    client_user = User(
        email="client_review@test.com",
        username="test_client",
        hashed_password="hashed_pass",
        role="client",
    )
    test_db.add(client_user)
    test_db.flush()

    client_profile = Client(user_id=client_user.id)
    test_db.add(client_profile)
    test_db.flush()

    # Create completed booking
    booking = Booking(
        client_id=client_profile.id,
        artisan_id=artisan.id,
        service="Test Service",
        estimated_cost=100.0,
        status=BookingStatus.COMPLETED,
    )
    test_db.add(booking)
    test_db.commit()
    test_db.refresh(booking)

    return booking


def test_create_review_success(client, test_booking, auth_headers, monkeypatch):
    """Test successful review creation"""
    # Mock the on-chain submission
    monkeypatch.setattr(
        "app.api.v1.endpoints.reviews.submit_reputation_on_chain",
        lambda artisan_address, stars: {"success": True, "hash": "test_hash"}
    )

    response = client.post(
        "/api/v1/reviews/create",
        json={
            "booking_id": str(test_booking.id),
            "artisan_id": test_booking.artisan_id,
            "rating": 5,
            "comment": "Excellent work!",
        },
        headers=auth_headers,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["rating"] == 5
    assert data["comment"] == "Excellent work!"
    assert data["artisan_id"] == test_booking.artisan_id


def test_create_review_duplicate(client, test_booking, auth_headers, monkeypatch):
    """Test that duplicate reviews are prevented"""
    monkeypatch.setattr(
        "app.api.v1.endpoints.reviews.submit_reputation_on_chain",
        lambda artisan_address, stars: {"success": True, "hash": "test_hash"}
    )

    # Create first review
    response1 = client.post(
        "/api/v1/reviews/create",
        json={
            "booking_id": str(test_booking.id),
            "artisan_id": test_booking.artisan_id,
            "rating": 4,
            "comment": "Good work",
        },
        headers=auth_headers,
    )
    assert response1.status_code == 201

    # Try to create duplicate
    response2 = client.post(
        "/api/v1/reviews/create",
        json={
            "booking_id": str(test_booking.id),
            "artisan_id": test_booking.artisan_id,
            "rating": 5,
            "comment": "Excellent work!",
        },
        headers=auth_headers,
    )
    assert response2.status_code == 409


def test_create_review_invalid_rating(client, test_booking, auth_headers):
    """Test that invalid ratings are rejected"""
    response = client.post(
        "/api/v1/reviews/create",
        json={
            "booking_id": str(test_booking.id),
            "artisan_id": test_booking.artisan_id,
            "rating": 6,  # Invalid rating
            "comment": "Bad rating",
        },
        headers=auth_headers,
    )
    assert response.status_code == 422  # Validation error


def test_create_review_incomplete_booking(client, test_db, auth_headers):
    """Test that reviews can only be created for completed bookings"""
    # Create incomplete booking
    booking = Booking(
        client_id=1,
        artisan_id=1,
        service="Test Service",
        estimated_cost=100.0,
        status=BookingStatus.PENDING,
    )
    test_db.add(booking)
    test_db.commit()
    test_db.refresh(booking)

    response = client.post(
        "/api/v1/reviews/create",
        json={
            "booking_id": str(booking.id),
            "artisan_id": booking.artisan_id,
            "rating": 5,
            "comment": "Premature review",
        },
        headers=auth_headers,
    )
    assert response.status_code == 400


def test_get_artisan_reviews(client, test_db):
    """Test retrieving all reviews for an artisan"""
    # Create some reviews
    review1 = Review(
        booking_id="00000000-0000-0000-0000-000000000001",
        client_id=1,
        artisan_id=1,
        rating=5,
        comment="Great!",
    )
    review2 = Review(
        booking_id="00000000-0000-0000-0000-000000000002",
        client_id=2,
        artisan_id=1,
        rating=4,
        comment="Good",
    )
    test_db.add_all([review1, review2])
    test_db.commit()

    response = client.get("/api/v1/reviews/artisan/1")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert all(r["artisan_id"] == 1 for r in data)
