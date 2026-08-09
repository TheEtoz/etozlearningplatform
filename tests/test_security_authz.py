"""Authorization boundaries for ownership, visibility, and class publish."""

from backend.models.user import User
from tests.helpers import make_question, register_and_login_headers


def _auth_headers(client, database_session, username: str) -> dict[str, str]:
    return register_and_login_headers(client, database_session, username)


def _make_admin(client, database_session, username: str) -> dict[str, str]:
    headers = _auth_headers(client, database_session, username)
    user_id = client.get("/api/v1/auth/me", headers=headers).json()["id"]
    user = database_session.get(User, user_id)
    user.role = "admin"
    database_session.commit()
    return headers


def test_teacher_cannot_manage_other_teachers_modules(
    client, database_session
) -> None:
    owner = _make_admin(client, database_session, "mod_owner")
    other = _make_admin(client, database_session, "mod_intruder")

    classroom = client.post(
        "/api/v1/classes",
        headers=owner,
        json={
            "title": "Owner Class",
            "description": "Mine",
            "visibility": "private",
        },
    ).json()
    module = client.post(
        "/api/v1/admin/modules",
        headers=owner,
        json={
            "class_id": classroom["id"],
            "title": "Owner Module",
            "description": "",
            "position": 0,
        },
    ).json()

    denied = client.put(
        f"/api/v1/admin/modules/{module['id']}/blocks",
        headers=other,
        json={"blocks": [{"type": "lecture", "payload": {"markdown": "hack"}}]},
    )
    assert denied.status_code == 403

    create_denied = client.post(
        "/api/v1/admin/modules",
        headers=other,
        json={
            "class_id": classroom["id"],
            "title": "Intruder Module",
            "description": "",
            "position": 1,
        },
    )
    assert create_denied.status_code == 403


def test_cannot_publish_another_teachers_private_quiz(
    client, database_session
) -> None:
    owner = _make_admin(client, database_session, "quiz_priv_owner")
    other = _make_admin(client, database_session, "quiz_priv_thief")

    private = client.post(
        "/api/v1/admin/quizzes",
        headers=owner,
        json={
            "title": "Secret Assessment",
            "description": "Private",
            "visibility": "private",
        },
    ).json()
    classroom = client.post(
        "/api/v1/classes",
        headers=other,
        json={
            "title": "Thief Class",
            "description": "Nope",
            "visibility": "private",
        },
    ).json()

    publish = client.put(
        f"/api/v1/classes/{classroom['id']}/quizzes",
        headers=other,
        json={"quiz_ids": [private["id"]]},
    )
    assert publish.status_code == 403


def test_private_question_hidden_from_student_routes(
    client, database_session
) -> None:
    teacher = _make_admin(client, database_session, "priv_q_teacher")
    student = _auth_headers(client, database_session, "priv_q_student")
    teacher_id = client.get("/api/v1/auth/me", headers=teacher).json()["id"]

    private = make_question(
        database_session,
        title="Hidden MCQ",
        description="Secret",
        topics=["basics"],
        choices=["a", "b"],
        correct_answer="a",
        visibility="private",
        owner_id=teacher_id,
    )
    database_session.commit()

    read = client.get(
        f"/api/v1/questions/{private.id}",
        headers=student,
    )
    assert read.status_code == 404

    check = client.post(
        f"/api/v1/questions/{private.id}/check",
        headers=student,
        json={"answer": "a"},
    )
    assert check.status_code == 404

    submit = client.post(
        "/api/v1/submissions",
        headers=student,
        json={"question_id": private.id, "answer": "a"},
    )
    assert submit.status_code == 403


def test_cannot_attach_others_private_question_to_quiz(
    client, database_session
) -> None:
    owner = _make_admin(client, database_session, "attach_owner")
    other = _make_admin(client, database_session, "attach_other")
    owner_id = client.get("/api/v1/auth/me", headers=owner).json()["id"]

    private = make_question(
        database_session,
        title="Owner Private Q",
        description="Mine",
        topics=["basics"],
        choices=["a", "b"],
        correct_answer="a",
        visibility="private",
        owner_id=owner_id,
    )
    database_session.commit()

    quiz = client.post(
        "/api/v1/admin/quizzes",
        headers=other,
        json={
            "title": "Other Quiz",
            "description": "Try attach",
            "visibility": "private",
        },
    ).json()
    attach = client.put(
        f"/api/v1/admin/quizzes/{quiz['id']}/questions",
        headers=other,
        json={"question_ids": [private.id]},
    )
    assert attach.status_code == 403
