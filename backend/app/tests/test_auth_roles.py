import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.main import app
from app.models.user import User

client = TestClient(app)

# Test data
TEST_USERS = {
    "client": {
        "email": "client@test.com",
        "password": "TestPass123!",
        "role": "client",
        "full_name": "Test Client",
    },
    "artisan": {
        "email": "artisan@test.com",
        "password": "TestPass123!",
        "role": "artisan",
        "full_name": "Test Artisan",
    },
    "admin": {
        "email": "admin@test.com",
        "password": "TestPass123!",
        "role": "admin",
        "full_name": "Test Admin",
    },
}


def create_test_token(user_id: int) -> str:
    """Create a test JWT token for a user"""
    return create_access_token(subject=user_id)


def get_auth_headers(token: str) -> dict:
    """Get authorization headers with Bearer token"""
    return {"Authorization": f"Bearer {token}"}


class TestRoleBasedAccess:
    """Test role-based access control across different endpoints"""

    def test_client_only_endpoints(self):
        """Test that client-only endpoints reject non-client users"""
        # This would require actual user creation and token generation
        # For demonstration purposes, showing the test structure

        # Test data for booking creation

        # Test cases:
        # 1. Client can create booking (should succeed)
        # 2. Artisan cannot create booking (should return 403)
        # 3. Admin cannot create booking (should return 403)
        # 4. Unauthenticated user cannot create booking (should return 401)

        pass  # Actual implementation would go here

    def test_artisan_only_endpoints(self):
        """Test that artisan-only endpoints reject non-artisan users"""

        # Test cases:
        # 1. Artisan can update profile (should succeed)
        # 2. Client cannot update profile (should return 403)
        # 3. Admin cannot update profile (should return 403)
        # 4. Unauthenticated user cannot update profile (should return 401)

        pass  # Actual implementation would go here

    def test_admin_only_endpoints(self):
        """Test that admin-only endpoints reject non-admin users"""

        # Test cases:
        # 1. Admin can list all users (should succeed)
        # 2. Client cannot list all users (should return 403)
        # 3. Artisan cannot list all users (should return 403)
        # 4. Unauthenticated user cannot list users (should return 401)

        pass  # Actual implementation would go here

    def test_multi_role_endpoints(self):
        """Test endpoints that allow multiple roles"""

        # Test /users/me endpoint (should allow all authenticated users)
        # Test /bookings/my-bookings (should allow clients and artisans)

        pass  # Actual implementation would go here

    def test_self_access_endpoints(self):
        """Test endpoints that allow admin or self access"""

        # Test /users/{user_id} endpoint
        # 1. User can access their own profile
        # 2. Admin can access any profile
        # 3. Other users cannot access different user's profile

        pass  # Actual implementation would go here


class TestAuthenticationErrors:
    """Test authentication error scenarios"""

    def test_no_token_provided(self):
        """Test endpoints without authentication token"""
        response = client.get("/api/v1/users/me")
        assert (
            response.status_code == 403
        )  # FastAPI HTTPBearer returns 403 for missing token

    def test_invalid_token_format(self):
        """Test endpoints with malformed token"""
        headers = {"Authorization": "Bearer invalid_token"}
        response = client.get("/api/v1/users/me", headers=headers)
        assert response.status_code == 401
        assert "Invalid token" in response.json()["detail"]

    def test_expired_token(self):
        """Test endpoints with expired token"""
        # Would need to create an expired token for testing
        pass

    def test_blacklisted_token(self):
        """Test endpoints with blacklisted token"""
        # Would need to create and blacklist a token for testing
        pass


class TestAuthorizationErrors:
    """Test authorization error scenarios"""

    def test_insufficient_permissions(self):
        """Test accessing endpoints with wrong role"""
        # This would test the 403 Forbidden responses
        pass

    def test_inactive_user_access(self):
        """Test that inactive users cannot access protected endpoints"""
        # Would need to create an inactive user and test access
        pass


# Example of how to run specific role-based tests
def test_booking_creation_role_access():
    """
    Example test demonstrating role-based access for booking creation
    This is a more concrete example of what the tests would look like
    """

    # Test data
    booking_data = {"service": "painting", "date": "2024-01-15"}

    # Test 1: No authentication (should fail with 401/403)
    response = client.post("/api/v1/bookings/create", json=booking_data)
    assert response.status_code in [401, 403]

    # Test 2: Invalid token (should fail with 401)
    headers = {"Authorization": "Bearer invalid_token"}
    response = client.post(
        "/api/v1/bookings/create", json=booking_data, headers=headers
    )
    assert response.status_code == 401

    # Additional tests would require actual user creation and authentication
    # which would be implemented in a full test suite


def test_admin_endpoints_access():
    """
    Example test for admin-only endpoints
    """

    # Test 1: No authentication
    response = client.get("/api/v1/admin/users")
    assert response.status_code in [401, 403]

    # Test 2: Invalid token
    headers = {"Authorization": "Bearer invalid_token"}
    response = client.get("/api/v1/admin/users", headers=headers)
    assert response.status_code == 401

    # Additional tests would require actual admin user and token


# Utility functions for test setup
def create_test_users(db: Session):
    """Create test users for all roles"""
    from app.core.security import get_password_hash

    for _role, user_data in TEST_USERS.items():
        user = User(
            email=user_data["email"],
            hashed_password=get_password_hash(user_data["password"]),
            role=user_data["role"],
            full_name=user_data["full_name"],
            is_active=True,
        )
        db.add(user)

    db.commit()


def cleanup_test_users(db: Session):
    """Clean up test users after tests"""
    for user_data in TEST_USERS.values():
        user = db.query(User).filter(User.email == user_data["email"]).first()
        if user:
            db.delete(user)
    db.commit()


# Pytest fixtures for test setup
@pytest.fixture
def test_db():
    """Fixture to provide test database session"""
    # This would be implemented with your test database setup
    pass


@pytest.fixture
def test_users(test_db):
    """Fixture to create test users"""
    create_test_users(test_db)
    yield
    cleanup_test_users(test_db)


@pytest.fixture
def client_token(test_users, test_db):
    """Fixture to provide client user token"""
    user = (
        test_db.query(User).filter(User.email == TEST_USERS["client"]["email"]).first()
    )
    return create_test_token(user.id)


@pytest.fixture
def artisan_token(test_users, test_db):
    """Fixture to provide artisan user token"""
    user = (
        test_db.query(User).filter(User.email == TEST_USERS["artisan"]["email"]).first()
    )
    return create_test_token(user.id)


@pytest.fixture
def admin_token(test_users, test_db):
    """Fixture to provide admin user token"""
    user = (
        test_db.query(User).filter(User.email == TEST_USERS["admin"]["email"]).first()
    )
    return create_test_token(user.id)
