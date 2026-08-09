"""Tests for admin question bank CRUD and authorization."""

from backend.config import get_settings
from backend.models.user import User
from tests.helpers import register_and_login_headers


def _register_and_login(client, database_session, username: str) -> dict[str, str]:
    return register_and_login_headers(client, database_session, username)


def _make_admin(client, database_session, username: str = "teacher") -> dict[str, str]:
    headers = _register_and_login(client, database_session, username)
    user_id = client.get("/api/v1/auth/me", headers=headers).json()["id"]
    user = database_session.get(User, user_id)
    user.role = "admin"
    database_session.commit()
    return headers


def test_student_cannot_create_question(client, database_session) -> None:
    headers = _register_and_login(client, database_session, "student_only")
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


def test_only_author_can_delete_and_private_is_hidden(
    client, database_session
) -> None:
    owner = _make_admin(client, database_session, "owner_teacher")
    other = _make_admin(client, database_session, "other_teacher")

    created = client.post(
        "/api/v1/admin/questions",
        headers=owner,
        json={
            "title": "Private bank item",
            "description": "Institution only",
            "difficulty": "easy",
            "type": "mcq",
            "topics": ["basics"],
            "visibility": "private",
            "choices": ["a", "b"],
            "correct_answer": "a",
        },
    ).json()
    assert created["visibility"] == "private"
    assert created["can_delete"] is True

    other_list = client.get("/api/v1/admin/questions", headers=other).json()
    assert all(item["id"] != created["id"] for item in other_list)

    forbidden = client.delete(
        f"/api/v1/admin/questions/{created['id']}",
        headers=other,
    )
    assert forbidden.status_code == 403

    allowed = client.delete(
        f"/api/v1/admin/questions/{created['id']}",
        headers=owner,
    )
    assert allowed.status_code == 204


def test_subject_areas_and_clone_keeps_original(client, database_session) -> None:
    owner = _make_admin(client, database_session, "bank_owner")
    other = _make_admin(client, database_session, "bank_user")

    subjects = client.get("/api/v1/admin/subjects", headers=owner)
    assert subjects.status_code == 200
    names = {item["name"] for item in subjects.json()}
    assert "python" in names

    created = client.post(
        "/api/v1/admin/questions",
        headers=owner,
        json={
            "title": "Shared loops",
            "description": "What prints?",
            "difficulty": "easy",
            "type": "mcq",
            "subject": "python",
            "topics": ["loops"],
            "visibility": "public",
            "choices": ["1", "2"],
            "correct_answer": "1",
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["subject"] == "python"
    assert body["topics"] == ["loops"]
    original_id = body["id"]

    cloned = client.post(
        f"/api/v1/admin/questions/{original_id}/clone",
        headers=other,
    )
    assert cloned.status_code == 201
    copy = cloned.json()
    assert copy["id"] != original_id
    assert copy["visibility"] == "private"
    assert copy["can_delete"] is True
    assert "(copy)" in copy["title"]

    edited = client.put(
        f"/api/v1/admin/questions/{copy['id']}",
        headers=other,
        json={"title": "My quiz loops", "correct_answer": "2"},
    )
    assert edited.status_code == 200
    assert edited.json()["correct_answer"] == "2"

    # Teachers may edit shared bank items (classroom workflows need fixes).
    shared_edit = client.put(
        f"/api/v1/admin/questions/{original_id}",
        headers=other,
        json={"title": "Shared loops (fixed)", "correct_answer": "1"},
    )
    assert shared_edit.status_code == 200
    assert shared_edit.json()["title"] == "Shared loops (fixed)"
    assert shared_edit.json()["can_edit"] is True

    # Delete remains author-only.
    forbidden_delete = client.delete(
        f"/api/v1/admin/questions/{original_id}",
        headers=other,
    )
    assert forbidden_delete.status_code == 403


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
