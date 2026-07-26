"""Tests for coding path and teacher quiz membership APIs."""

from backend.models.user import User
from tests.helpers import make_question


def _auth_headers(client, username: str) -> dict[str, str]:
    client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": "password123",
        },
    )
    login = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "password123"},
    )
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _make_admin(client, database_session, username: str) -> dict[str, str]:
    headers = _auth_headers(client, username)
    user_id = client.get("/api/v1/auth/me", headers=headers).json()["id"]
    user = database_session.get(User, user_id)
    user.role = "admin"
    database_session.commit()
    return headers


def test_admin_can_build_quiz_membership(client, database_session) -> None:
    headers = _make_admin(client, database_session, "quiz_builder")
    q1 = make_question(
        database_session,
        title="Bank Q1",
        description="MCQ",
        topics=["basics"],
        choices=["a", "b"],
        correct_answer="a",
    )
    q2 = make_question(
        database_session,
        title="Bank Q2",
        description="Coding",
        question_type="coding",
        topics=["basics", "loops"],
        starter_code='print("x")\n',
        test_cases=[{"stdin": "", "expected_stdout": "x"}],
    )
    database_session.commit()

    created = client.post(
        "/api/v1/admin/quizzes",
        headers=headers,
        json={
            "title": "Mixed Pack",
            "description": "MCQ + coding",
            "is_timed": True,
            "duration_seconds": 90,
        },
    )
    assert created.status_code == 201
    quiz_id = created.json()["id"]

    membership = client.put(
        f"/api/v1/admin/quizzes/{quiz_id}/questions",
        headers=headers,
        json={"question_ids": [q1.id, q2.id]},
    )
    assert membership.status_code == 200
    assert membership.json()["question_ids"] == [q1.id, q2.id]
    assert set(membership.json()["topics"]) == {"basics", "loops"}


def test_admin_can_create_topic(client, database_session) -> None:
    headers = _make_admin(client, database_session, "topic_builder")
    response = client.post(
        "/api/v1/admin/topics",
        headers=headers,
        json={"name": "Recursion"},
    )
    assert response.status_code == 201
    assert response.json()["name"] == "recursion"


def test_coding_path_lists_modules_and_levels(client, database_session) -> None:
    headers = _make_admin(client, database_session, "path_builder")
    student = _auth_headers(client, "path_student")

    coding = make_question(
        database_session,
        title="Path Hello",
        description="Print hi",
        question_type="coding",
        topics=["basics"],
        starter_code='print("hi")\n',
        test_cases=[{"stdin": "", "expected_stdout": "hi"}],
    )
    database_session.commit()

    module = client.post(
        "/api/v1/admin/modules",
        headers=headers,
        json={
            "title": "Module Basics",
            "description": "Start here",
            "position": 0,
            "difficulty_label": "Beginner",
        },
    ).json()
    client.put(
        f"/api/v1/admin/modules/{module['id']}/levels",
        headers=headers,
        json={"question_ids": [coding.id]},
    )

    path = client.get("/api/v1/path", headers=student)
    assert path.status_code == 200
    assert path.json()[0]["title"] == "Module Basics"
    assert path.json()[0]["levels"][0]["question_id"] == coding.id
    assert path.json()[0]["levels"][0]["is_completed"] is False
