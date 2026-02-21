from app.models.user import User


def test_register_user(client):
    test_user_data = {
        "email": "testuser@example.com",
        "password": "StrongPass1!",
        "role": "client",
        "full_name": "Test User",
        "phone": "1234567890",
        "username": "testuser",
    }
    response = client.post("api/v1/auth/register", json=test_user_data)
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert data["role"] == "client"


def test_login_user(client):
    test_user_data = {
        "email": "testuser2@example.com",
        "password": "StrongPass1!",
        "role": "client",
    }
    client.post("api/v1/auth/register", json=test_user_data)

    login_data = {"email": "testuser2@example.com", "password": "StrongPass1!"}
    response = client.post("api/v1/auth/login", json=login_data)
    assert response.status_code == 200
    tokens = response.json()
    assert "access_token" in tokens
    assert "refresh_token" in tokens


def test_logout_user(client):
    test_user_data = {
        "email": "testuser3@example.com",
        "password": "StrongPass1!",
        "role": "client",
    }
    client.post("api/v1/auth/register", json=test_user_data)

    login_data = {"email": "testuser3@example.com", "password": "StrongPass1!"}
    login_resp = client.post("api/v1/auth/login", json=login_data)
    tokens = login_resp.json()

    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    response = client.post("api/v1/auth/logout", headers=headers)
    assert response.status_code == 200
    assert response.json()["message"] == "Successfully logged out"


def test_cannot_self_register_as_admin(client):
    response = client.post(
        "api/v1/auth/register",
        json={
            "email": "attacker@example.com",
            "password": "Attack3r!",
            "role": "admin",
        },
    )
    assert response.status_code == 422


def test_can_register_as_client(client):
    response = client.post(
        "api/v1/auth/register",
        json={
            "email": "valid_client@example.com",
            "password": "Valid1Pw!",
            "role": "client",
        },
    )
    assert response.status_code == 201
    assert response.json()["role"] == "client"


def test_can_register_as_artisan(client):
    response = client.post(
        "api/v1/auth/register",
        json={
            "email": "craft@example.com",
            "password": "Valid1Pw!",
            "role": "artisan",
        },
    )
    assert response.status_code == 201
    assert response.json()["role"] == "artisan"


def test_no_admin_created_via_public_registration(client, db_session):
    response = client.post(
        "api/v1/auth/register",
        json={
            "email": "attempt@example.com",
            "password": "Attack3r!",
            "role": "admin",
        },
    )
    assert response.status_code == 422

    admin_count = db_session.query(User).filter(User.role == "admin").count()
    assert admin_count == 0


def test_unknown_role_rejected(client):
    response = client.post(
        "api/v1/auth/register",
        json={
            "email": "unknown-role@example.com",
            "password": "Valid1Pw!",
            "role": "superuser",
        },
    )
    assert response.status_code == 422
