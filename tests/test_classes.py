"""Tests for class management, enrollment, and class-scoped content."""

from backend.models.user import User
from tests.helpers import (
    make_quiz_with_questions,
    make_question,
    register_and_login_headers,
)


def _auth_headers(client, database_session, username: str) -> dict[str, str]:
    return register_and_login_headers(client, database_session, username)


def _make_admin(client, database_session, username: str) -> dict[str, str]:
    headers = _auth_headers(client, database_session, username)
    user_id = client.get("/api/v1/auth/me", headers=headers).json()["id"]
    user = database_session.get(User, user_id)
    user.role = "admin"
    database_session.commit()
    return headers


def test_teacher_creates_class_with_code(client, database_session) -> None:
    teacher = _make_admin(client, database_session, "class_owner")
    response = client.post(
        "/api/v1/classes",
        headers=teacher,
        json={
            "title": "CS101",
            "description": "Intro Python",
            "visibility": "private",
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "CS101"
    assert body["visibility"] == "private"
    assert body["enrollment_code"]
    assert len(body["enrollment_code"]) == 8


def test_owner_can_delete_class(client, database_session) -> None:
    teacher = _make_admin(client, database_session, "delete_owner")
    other = _make_admin(client, database_session, "delete_other")
    created = client.post(
        "/api/v1/classes",
        headers=teacher,
        json={
            "title": "Temp Class",
            "description": "Will be deleted",
            "visibility": "private",
        },
    ).json()
    class_id = created["id"]

    forbidden = client.delete(
        f"/api/v1/classes/{class_id}",
        headers=other,
    )
    assert forbidden.status_code in (403, 404)

    deleted = client.delete(
        f"/api/v1/classes/{class_id}",
        headers=teacher,
    )
    assert deleted.status_code == 204

    missing = client.get(
        f"/api/v1/classes/{class_id}",
        headers=teacher,
    )
    assert missing.status_code == 404

    mine = client.get("/api/v1/classes/mine", headers=teacher)
    assert mine.status_code == 200
    assert all(item["id"] != class_id for item in mine.json())


def test_owner_can_reactivate_inactive_class(client, database_session) -> None:
    teacher = _make_admin(client, database_session, "reactivate_owner")
    created = client.post(
        "/api/v1/classes",
        headers=teacher,
        json={
            "title": "Pause Me",
            "description": "Will deactivate",
            "visibility": "private",
        },
    ).json()
    class_id = created["id"]

    paused = client.patch(
        f"/api/v1/classes/{class_id}",
        headers=teacher,
        json={"is_active": False},
    )
    assert paused.status_code == 200
    assert paused.json()["is_active"] is False

    resumed = client.patch(
        f"/api/v1/classes/{class_id}",
        headers=teacher,
        json={"is_active": True},
    )
    assert resumed.status_code == 200
    assert resumed.json()["is_active"] is True

    # Students still cannot open an inactive class.
    client.patch(
        f"/api/v1/classes/{class_id}",
        headers=teacher,
        json={"is_active": False},
    )
    student = _auth_headers(client, database_session, "reactivate_student")
    denied = client.get(f"/api/v1/classes/{class_id}", headers=student)
    assert denied.status_code == 404


def test_public_enroll_and_private_requires_code(client, database_session) -> None:
    teacher = _make_admin(client, database_session, "enroll_teacher")
    public = client.post(
        "/api/v1/classes",
        headers=teacher,
        json={
            "title": "Open Lab",
            "description": "Anyone can join",
            "visibility": "public",
        },
    ).json()
    private = client.post(
        "/api/v1/classes",
        headers=teacher,
        json={
            "title": "Closed Lab",
            "description": "Code only",
            "visibility": "private",
        },
    ).json()

    student = _auth_headers(client, database_session, "enroll_student")
    browse = client.get("/api/v1/classes/public", headers=student)
    assert browse.status_code == 200
    assert any(item["id"] == public["id"] for item in browse.json())
    assert all(item["id"] != private["id"] for item in browse.json())

    bad_public = client.post(
        "/api/v1/classes/enroll",
        headers=student,
        json={"class_id": private["id"]},
    )
    assert bad_public.status_code == 400

    ok_public = client.post(
        "/api/v1/classes/enroll",
        headers=student,
        json={"class_id": public["id"]},
    )
    assert ok_public.status_code == 200

    via_code = client.post(
        "/api/v1/classes/enroll",
        headers=_auth_headers(client, database_session, "code_student"),
        json={"code": private["enrollment_code"]},
    )
    assert via_code.status_code == 200
    assert via_code.json()["id"] == private["id"]


def test_unpublished_quiz_not_visible_and_performance_scoped(
    client,
    database_session,
) -> None:
    teacher = _make_admin(client, database_session, "perf_teacher")
    quiz = make_quiz_with_questions(database_session)
    coding = make_question(
        database_session,
        title="Class Hello",
        description="hi",
        question_type="coding",
        topics=["basics"],
        starter_code='print("hi")\n',
        test_cases=[{"stdin": "", "expected_stdout": "hi"}],
    )
    database_session.commit()

    classroom = client.post(
        "/api/v1/classes",
        headers=teacher,
        json={
            "title": "Perf Class",
            "description": "Track students",
            "visibility": "public",
        },
    ).json()
    class_id = classroom["id"]

    module = client.post(
        "/api/v1/admin/modules",
        headers=teacher,
        json={
            "class_id": class_id,
            "title": "Class Module",
            "description": "Levels",
            "position": 0,
            "difficulty_label": "Beginner",
        },
    ).json()
    client.put(
        f"/api/v1/admin/modules/{module['id']}/levels",
        headers=teacher,
        json={"question_ids": [coding.id]},
    )

    student = _auth_headers(client, database_session, "perf_student")
    client.post(
        "/api/v1/classes/enroll",
        headers=student,
        json={"code": classroom["enrollment_code"]},
    )

    empty = client.get(
        f"/api/v1/classes/{class_id}/quizzes",
        headers=student,
    )
    assert empty.status_code == 200
    assert empty.json() == []

    client.put(
        f"/api/v1/classes/{class_id}/quizzes",
        headers=teacher,
        json={"quiz_ids": [quiz.id]},
    )

    questions = client.get(
        f"/api/v1/classes/{class_id}/quizzes/{quiz.id}/questions",
        headers=student,
    ).json()
    client.post(
        f"/api/v1/classes/{class_id}/quizzes/{quiz.id}/complete",
        headers=student,
        json={
            "answers": [
                {"question_id": questions[0]["id"], "answer": "5"},
                {"question_id": questions[1]["id"], "answer": "6"},
            ]
        },
    )

    performance = client.get(
        f"/api/v1/classes/{class_id}/performance",
        headers=teacher,
    )
    assert performance.status_code == 200
    row = performance.json()[0]
    assert row["quizzes_completed"] == 1
    assert row["quizzes_published"] == 1
    assert float(row["average_best_score"]) == 100.0
    assert row["coding_levels_total"] == 1
    assert row["coding_levels_passed"] == 0


def test_student_cannot_create_class(client, database_session) -> None:
    student = _auth_headers(client, database_session, "no_create")
    response = client.post(
        "/api/v1/classes",
        headers=student,
        json={
            "title": "Nope",
            "description": "Students cannot create",
            "visibility": "public",
        },
    )
    assert response.status_code == 403
