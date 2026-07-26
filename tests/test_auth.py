"""Tests for Step 3 authentication."""

from backend.models.user import User
from backend.security import hash_password, verify_password


def test_passwords_are_hashed_and_verifiable() -> None:
    """Passwords should be stored as hashes, not plain text."""

    hashed = hash_password("student-password")

    assert hashed != "student-password"
    assert verify_password("student-password", hashed) is True
    assert verify_password("wrong-password", hashed) is False


def test_register_login_and_me_flow(client) -> None:
    """Users can register, log in, and fetch their profile."""

    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "username": "alice",
            "email": "alice@example.com",
            "password": "password123",
        },
    )
    assert register_response.status_code == 201
    assert register_response.json()["username"] == "alice"
    assert "hashed_password" not in register_response.json()

    login_response = client.post(
        "/api/v1/auth/login",
        json={"username": "alice", "password": "password123"},
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    me_response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "alice@example.com"


def test_me_requires_authentication(client) -> None:
    """Protected routes should reject requests without a token."""

    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401


def test_duplicate_username_returns_400(client) -> None:
    """Registering the same username twice should fail."""

    payload = {
        "username": "bob",
        "email": "bob@example.com",
        "password": "password123",
    }
    first_response = client.post("/api/v1/auth/register", json=payload)
    second_response = client.post(
        "/api/v1/auth/register",
        json={
            "username": "bob",
            "email": "other@example.com",
            "password": "password123",
        },
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 400
    assert second_response.json()["detail"] == "Username already registered"


def test_duplicate_email_returns_400(client) -> None:
    """Registering the same email twice should fail."""

    first_response = client.post(
        "/api/v1/auth/register",
        json={
            "username": "carol",
            "email": "carol@example.com",
            "password": "password123",
        },
    )
    second_response = client.post(
        "/api/v1/auth/register",
        json={
            "username": "carol2",
            "email": "carol@example.com",
            "password": "password123",
        },
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 400
    assert second_response.json()["detail"] == "Email already registered"


def test_login_with_wrong_password_returns_401(client, database_session) -> None:
    """Invalid credentials should not return a token."""

    user = User(
        username="dave",
        email="dave@example.com",
        hashed_password=hash_password("correct-password"),
    )
    database_session.add(user)
    database_session.commit()

    response = client.post(
        "/api/v1/auth/login",
        json={"username": "dave", "password": "wrong-password"},
    )

    assert response.status_code == 401
