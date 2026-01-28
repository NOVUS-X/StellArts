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
