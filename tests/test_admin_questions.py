"""Tests for admin question bank CRUD and authorization."""

from backend.config import get_settings
from backend.models.user import User


def _register_and_login(client, username: str) -> dict[str, str]:
    client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": "password123",
        },
    )
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "password123"},
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _make_admin(client, database_session, username: str = "teacher") -> dict[str, str]:
    headers = _register_and_login(client, username)
    user_id = client.get("/api/v1/auth/me", headers=headers).json()["id"]
    user = database_session.get(User, user_id)
    user.role = "admin"
    database_session.commit()
    return headers


def test_student_cannot_create_question(client) -> None:
    headers = _register_and_login(client, "student_only")
    response = client.post(
        "/api/v1/admin/questions",
        headers=headers,
        json={
            "title": "Blocked MCQ",
            "description": "Should fail",
            "difficulty": "easy",
            "type": "mcq",
            "topics": ["basics"],
            "choices": ["A", "B"],
            "correct_answer": "A",
        },
    )
    assert response.status_code == 403


def test_admin_can_create_mcq_and_coding(client, database_session) -> None:
    headers = _make_admin(client, database_session)

    mcq = client.post(
        "/api/v1/admin/questions",
        headers=headers,
        json={
            "title": "Admin MCQ",
            "description": "2+2?",
            "difficulty": "easy",
            "type": "mcq",
            "topics": ["operators", "basics"],
            "choices": ["3", "4"],
            "correct_answer": "4",
        },
    )
    assert mcq.status_code == 201
    assert mcq.json()["correct_answer"] == "4"
    assert set(mcq.json()["topics"]) == {"operators", "basics"}

    coding = client.post(
        "/api/v1/admin/questions",
        headers=headers,
        json={
            "title": "Admin Coding",
            "description": "Print hi",
            "difficulty": "easy",
            "type": "coding",
            "topics": ["basics"],
            "starter_code": 'print("hi")\n',
            "test_cases": [{"stdin": "", "expected_stdout": "hi"}],
        },
    )
    assert coding.status_code == 201
    assert coding.json()["test_cases"][0]["expected_stdout"] == "hi"

    managed = client.get("/api/v1/admin/questions", headers=headers)
    assert managed.status_code == 200
    assert len(managed.json()) >= 2


def test_admin_can_update_and_delete_question(client, database_session) -> None:
    headers = _make_admin(client, database_session, "editor")
    created = client.post(
        "/api/v1/admin/questions",
        headers=headers,
        json={
            "title": "Temp question",
            "description": "Delete me",
            "difficulty": "easy",
            "type": "mcq",
            "topics": ["basics"],
            "choices": ["yes", "no"],
            "correct_answer": "yes",
        },
    ).json()

    updated = client.put(
        f"/api/v1/admin/questions/{created['id']}",
        headers=headers,
        json={"title": "Renamed question"},
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Renamed question"

    deleted = client.delete(
        f"/api/v1/admin/questions/{created['id']}",
        headers=headers,
    )
    assert deleted.status_code == 204


def test_bootstrap_admin_username_from_settings(client, monkeypatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "admin_usernames", ["boot_admin"])

    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": "boot_admin",
            "email": "boot@example.com",
            "password": "password123",
        },
    )
    assert response.status_code == 201
    assert response.json()["role"] == "admin"
