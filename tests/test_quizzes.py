"""Tests for class-scoped quizzes and persisted student scores."""

from backend.models.progress import Progress
from backend.models.quiz_attempt import QuizAttempt
from backend.models.submission import Submission
from backend.models.user import User
from tests.helpers import make_quiz_with_questions, register_and_login_headers


def _auth_headers(client, database_session, username: str = "quiz_tester") -> dict[str, str]:
    return register_and_login_headers(client, database_session, username)


def _make_admin(client, database_session, username: str) -> dict[str, str]:
    headers = _auth_headers(client, database_session, username)
    user_id = client.get("/api/v1/auth/me", headers=headers).json()["id"]
    user = database_session.get(User, user_id)
    user.role = "admin"
    database_session.commit()
    return headers


def _publish_quiz_in_class(client, database_session, quiz_id: int) -> tuple[dict, int]:
    teacher = _make_admin(client, database_session, "quiz_teacher")
    created = client.post(
        "/api/v1/classes",
        headers=teacher,
        json={
            "title": "Quiz Class",
            "description": "Class for quiz tests",
            "visibility": "public",
        },
    )
    assert created.status_code == 201
    class_id = created.json()["id"]
    code = created.json()["enrollment_code"]
    publish = client.put(
        f"/api/v1/classes/{class_id}/quizzes",
        headers=teacher,
        json={"quiz_ids": [quiz_id]},
    )
    assert publish.status_code == 200
    return {"code": code, "class_id": class_id}, class_id


def test_global_quiz_catalog_is_empty(client, database_session) -> None:
    make_quiz_with_questions(database_session, is_timed=True)
    response = client.get("/api/v1/quizzes", headers=_auth_headers(client, database_session))
    assert response.status_code == 200
    assert response.json() == []


def test_class_quiz_cards_expose_teacher_timing(client, database_session) -> None:
    quiz = make_quiz_with_questions(database_session, is_timed=True)
    meta, class_id = _publish_quiz_in_class(client, database_session, quiz.id)
    student = _auth_headers(client, database_session, "timing_student")
    enroll = client.post(
        "/api/v1/classes/enroll",
        headers=student,
        json={"code": meta["code"]},
    )
    assert enroll.status_code == 200

    response = client.get(
        f"/api/v1/classes/{class_id}/quizzes",
        headers=student,
    )
    assert response.status_code == 200
    card = response.json()[0]
    assert card["is_timed"] is True
    assert card["duration_seconds"] == 60
    assert card["question_count"] == 2
    assert card["is_completed"] is False
    assert "operators" in card["topics"]


def test_complete_class_quiz_saves_score_and_allows_redo(
    client,
    database_session,
) -> None:
    quiz = make_quiz_with_questions(database_session, is_timed=False)
    meta, class_id = _publish_quiz_in_class(client, database_session, quiz.id)
    headers = _auth_headers(client, database_session, "complete_student")
    client.post(
        "/api/v1/classes/enroll",
        headers=headers,
        json={"code": meta["code"]},
    )

    questions = client.get(
        f"/api/v1/classes/{class_id}/quizzes/{quiz.id}/questions",
        headers=headers,
    ).json()
    assert "correct_answer" not in questions[0]
    assert "topics" in questions[0]

    first = client.post(
        f"/api/v1/classes/{class_id}/quizzes/{quiz.id}/complete",
        headers=headers,
        json={
            "answers": [
                {"question_id": questions[0]["id"], "answer": "5"},
                {"question_id": questions[1]["id"], "answer": "5"},
            ]
        },
    )
    assert first.status_code == 200
    assert first.json()["attempt_id"] > 0
    assert float(first.json()["score"]) == 50.0
    assert first.json()["results"][1]["correct_answer"] == "6"

    catalog = client.get(
        f"/api/v1/classes/{class_id}/quizzes",
        headers=headers,
    ).json()
    assert catalog[0]["is_completed"] is True
    assert catalog[0]["attempt_count"] == 1
    assert float(catalog[0]["best_score"]) == 50.0
    assert float(catalog[0]["last_score"]) == 50.0

    second = client.post(
        f"/api/v1/classes/{class_id}/quizzes/{quiz.id}/complete",
        headers=headers,
        json={
            "answers": [
                {"question_id": questions[0]["id"], "answer": "5"},
                {"question_id": questions[1]["id"], "answer": "6"},
            ]
        },
    )
    assert second.status_code == 200
    assert float(second.json()["score"]) == 100.0

    catalog_after_redo = client.get(
        f"/api/v1/classes/{class_id}/quizzes",
        headers=headers,
    ).json()
    assert catalog_after_redo[0]["attempt_count"] == 2
    assert float(catalog_after_redo[0]["best_score"]) == 100.0
    assert float(catalog_after_redo[0]["last_score"]) == 100.0

    attempts = database_session.query(QuizAttempt).all()
    assert len(attempts) == 2
    assert all(item.class_id == class_id for item in attempts)
    assert database_session.query(Submission).count() == 4
    progress = database_session.query(Progress).one()
    assert progress.topic == "operators"
    assert progress.questions_attempted == 4
    assert progress.questions_correct == 3
