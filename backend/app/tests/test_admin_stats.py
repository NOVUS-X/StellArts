"""
Integration tests for admin statistics endpoint.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash
from app.models.user import User


@pytest.fixture
def admin_user(db_session):
    """Create an admin user for testing."""
    admin = User(
        email="admin@test.com",
        hashed_password=get_password_hash("AdminPass123!"),
        full_name="Test Admin",
        role="admin",
        is_active=True,
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)
    return admin


@pytest.fixture
def admin_token(admin_user):
    """Create an admin token for testing."""
    return create_access_token(subject=admin_user.id)


@pytest.fixture
def client_user(db_session):
    """Create a client user for testing."""
    client_user = User(
        email="client@test.com",
        hashed_password=get_password_hash("ClientPass123!"),
        full_name="Test Client",
        role="client",
        is_active=True,
    )
    db_session.add(client_user)
    db_session.commit()
    db_session.refresh(client_user)
    return client_user


@pytest.fixture
def client_token(client_user):
    """Create a client token for testing."""
    return create_access_token(subject=client_user.id)


def test_admin_stats_active_users_count(client: TestClient, db_session: Session, admin_token: str):
    """Test that active_users count is accurate in system statistics."""
    # Create test users with different active states
    active_user_1 = User(
        email="active1@example.com",
        hashed_password="hashed",
        full_name="Active User 1",
        role="client",
        is_active=True,
    )
    active_user_2 = User(
        email="active2@example.com",
        hashed_password="hashed",
        full_name="Active User 2",
        role="artisan",
        is_active=True,
    )
    inactive_user = User(
        email="inactive@example.com",
        hashed_password="hashed",
        full_name="Inactive User",
        role="client",
        is_active=False,
    )
    
    db_session.add_all([active_user_1, active_user_2, inactive_user])
    db_session.commit()
    
    # Call the admin stats endpoint
    response = client.get(
        "/api/v1/admin/stats",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify stats structure
    assert "stats" in data
    stats = data["stats"]
    
    # Count active users in database (including the admin user from fixture)
    total_active = db_session.query(User).filter(User.is_active == True).count()
    total_inactive = db_session.query(User).filter(User.is_active == False).count()
    total_users = db_session.query(User).count()
    
    # Assert active_users is greater than 0 and matches database
    assert stats["active_users"] > 0, "active_users should be greater than 0"
    assert stats["active_users"] == total_active
    assert stats["inactive_users"] == total_inactive
    assert stats["total_users"] == total_users
    assert stats["active_users"] + stats["inactive_users"] == stats["total_users"]


def test_admin_stats_role_distribution(client: TestClient, db_session: Session, admin_token: str):
    """Test that role distribution is accurate in system statistics."""
    # Create users with different roles
    client_user = User(
        email="client@example.com",
        hashed_password="hashed",
        full_name="Client User",
        role="client",
        is_active=True,
    )
    artisan_user = User(
        email="artisan@example.com",
        hashed_password="hashed",
        full_name="Artisan User",
        role="artisan",
        is_active=True,
    )
    
    db_session.add_all([client_user, artisan_user])
    db_session.commit()
    
    # Call the admin stats endpoint
    response = client.get(
        "/api/v1/admin/stats",
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    
    assert response.status_code == 200
    data = response.json()
    
    # Verify role distribution
    stats = data["stats"]
    assert "role_distribution" in stats
    
    clients_count = db_session.query(User).filter(User.role == "client").count()
    artisans_count = db_session.query(User).filter(User.role == "artisan").count()
    admins_count = db_session.query(User).filter(User.role == "admin").count()
    
    assert stats["role_distribution"]["clients"] == clients_count
    assert stats["role_distribution"]["artisans"] == artisans_count
    assert stats["role_distribution"]["admins"] == admins_count


def test_admin_stats_requires_admin_role(client: TestClient, client_token: str):
    """Test that non-admin users cannot access system statistics."""
    response = client.get(
        "/api/v1/admin/stats",
        headers={"Authorization": f"Bearer {client_token}"}
    )
    
    assert response.status_code == 403
