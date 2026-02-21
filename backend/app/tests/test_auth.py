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
    response = client.post(
        "api/v1/auth/logout",
        headers=headers,
        json={"refresh_token": tokens["refresh_token"]},
    )
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


def test_refresh_token_returns_new_access_token(client):
    test_user_data = {
        "email": "refreshuser@example.com",
        "password": "StrongPass1!",
        "role": "client",
    }
    client.post("api/v1/auth/register", json=test_user_data)

    login_resp = client.post(
        "api/v1/auth/login",
        json={"email": "refreshuser@example.com", "password": "StrongPass1!"},
    )
    tokens = login_resp.json()

    refresh_resp = client.post(
        "api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refresh_resp.status_code == 200
    refreshed = refresh_resp.json()
    assert "access_token" in refreshed
    assert refreshed["refresh_token"] == tokens["refresh_token"]


def test_cannot_refresh_after_logout(client, monkeypatch):
    revoked_jtis = set()

    def fake_blacklist_token(jti: str, _exp: int):
        revoked_jtis.add(jti)

    def fake_is_token_blacklisted(jti: str) -> bool:
        return jti in revoked_jtis

    monkeypatch.setattr(
        "app.api.v1.endpoints.auth.blacklist_token", fake_blacklist_token
    )
    monkeypatch.setattr(
        "app.api.v1.endpoints.auth.is_token_blacklisted", fake_is_token_blacklisted
    )

    test_user_data = {
        "email": "logoutrefresh@example.com",
        "password": "StrongPass1!",
        "role": "client",
    }
    client.post("api/v1/auth/register", json=test_user_data)

    login_resp = client.post(
        "api/v1/auth/login",
        json={"email": "logoutrefresh@example.com", "password": "StrongPass1!"},
    )
    tokens = login_resp.json()

    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    logout_resp = client.post(
        "api/v1/auth/logout",
        headers=headers,
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert logout_resp.status_code == 200

    refresh_resp = client.post(
        "api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refresh_resp.status_code == 401
    assert "revoked" in refresh_resp.json()["detail"].lower()
