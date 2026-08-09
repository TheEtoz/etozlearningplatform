"""Tests for authentication, email verification, and password reset."""

from datetime import UTC, datetime, timedelta

from backend.models.auth_token import AuthEmailToken
from backend.models.user import User
from backend.security import hash_password, hash_url_token, verify_password
from tests.helpers import mark_email_verified


def test_passwords_are_hashed_and_verifiable() -> None:
    """Passwords should be stored as hashes, not plain text."""

    hashed = hash_password("student-password")

    assert hashed != "student-password"
    assert verify_password("student-password", hashed) is True
    assert verify_password("wrong-password", hashed) is False


def test_register_can_login_immediately(client, database_session) -> None:
    """New accounts can log in without email confirmation."""

    del database_session  # unused; kept for fixture parity with other auth tests
    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "username": "alice",
            "email": "alice@example.com",
            "password": "password123",
        },
    )
    assert register_response.status_code == 201
    body = register_response.json()
    assert body["username"] == "alice"
    assert body["email_verified"] is True
    assert "hashed_password" not in body

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
    assert me_response.json()["email_verified"] is True


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
        email_verified=True,
    )
    database_session.add(user)
    database_session.commit()

    response = client.post(
        "/api/v1/auth/login",
        json={"username": "dave", "password": "wrong-password"},
    )

    assert response.status_code == 401


def test_forgot_and_reset_password(client, database_session) -> None:
    client.post(
        "/api/v1/auth/register",
        json={
            "username": "erin",
            "email": "erin@example.com",
            "password": "password123",
        },
    )
    mark_email_verified(database_session, "erin")

    forgot = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "erin@example.com"},
    )
    assert forgot.status_code == 200
    assert "sent" in forgot.json()["message"].lower() or "account" in forgot.json()[
        "message"
    ].lower()

    # Unknown email still returns generic success.
    unknown = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": "nobody@example.com"},
    )
    assert unknown.status_code == 200

    reset_row = (
        database_session.query(AuthEmailToken)
        .filter(AuthEmailToken.purpose == "reset")
        .one()
    )
    raw = "test-reset-token-erin-1234567890"
    reset_row.token_hash = hash_url_token(raw)
    reset_row.expires_at = datetime.now(UTC) + timedelta(hours=1)
    reset_row.used_at = None
    database_session.commit()

    reset = client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw, "new_password": "newpassword99"},
    )
    assert reset.status_code == 200

    reused = client.post(
        "/api/v1/auth/reset-password",
        json={"token": raw, "new_password": "anotherpass99"},
    )
    assert reused.status_code == 400

    old_login = client.post(
        "/api/v1/auth/login",
        json={"username": "erin", "password": "password123"},
    )
    assert old_login.status_code == 401

    new_login = client.post(
        "/api/v1/auth/login",
        json={"username": "erin", "password": "newpassword99"},
    )
    assert new_login.status_code == 200


def test_expired_verify_token_rejected(client, database_session) -> None:
    """Legacy verify-email endpoint still rejects expired tokens."""

    client.post(
        "/api/v1/auth/register",
        json={
            "username": "frank",
            "email": "frank@example.com",
            "password": "password123",
        },
    )
    user = database_session.query(User).filter(User.username == "frank").one()
    raw = "expired-verify-token-frank-123456"
    database_session.add(
        AuthEmailToken(
            user_id=user.id,
            purpose="verify",
            token_hash=hash_url_token(raw),
            expires_at=datetime.now(UTC) - timedelta(hours=1),
        )
    )
    database_session.commit()

    response = client.post(
        "/api/v1/auth/verify-email",
        json={"token": raw},
    )
    assert response.status_code == 400
