"""Tests for bank-backed quizzes and persisted student scores."""

from backend.models.progress import Progress
from backend.models.quiz_attempt import QuizAttempt
from backend.models.submission import Submission
from tests.helpers import make_quiz_with_questions


def _auth_headers(client, username: str = "quiz_tester") -> dict[str, str]:
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


def test_quiz_cards_expose_teacher_timing(client, database_session) -> None:
    make_quiz_with_questions(database_session, is_timed=True)
    response = client.get("/api/v1/quizzes", headers=_auth_headers(client))

    assert response.status_code == 200
    card = response.json()[0]
    assert card["is_timed"] is True
    assert card["duration_seconds"] == 60
    assert card["question_count"] == 2
    assert card["is_completed"] is False
    assert "operators" in card["topics"]


def test_complete_quiz_saves_score_and_allows_redo(
    client,
    database_session,
) -> None:
    quiz = make_quiz_with_questions(database_session, is_timed=False)
    headers = _auth_headers(client)

    questions = client.get(
        f"/api/v1/quizzes/{quiz.id}/questions",
        headers=headers,
    ).json()
    assert "correct_answer" not in questions[0]
    assert "topics" in questions[0]

    first = client.post(
        f"/api/v1/quizzes/{quiz.id}/complete",
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

    catalog = client.get("/api/v1/quizzes", headers=headers).json()
    assert catalog[0]["is_completed"] is True
    assert catalog[0]["attempt_count"] == 1
    assert float(catalog[0]["best_score"]) == 50.0
    assert float(catalog[0]["last_score"]) == 50.0

    second = client.post(
        f"/api/v1/quizzes/{quiz.id}/complete",
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

    catalog_after_redo = client.get("/api/v1/quizzes", headers=headers).json()
    assert catalog_after_redo[0]["attempt_count"] == 2
    assert float(catalog_after_redo[0]["best_score"]) == 100.0
    assert float(catalog_after_redo[0]["last_score"]) == 100.0

    assert database_session.query(QuizAttempt).count() == 2
    assert database_session.query(Submission).count() == 4
    progress = database_session.query(Progress).one()
    assert progress.topic == "operators"
    assert progress.questions_attempted == 4
    assert progress.questions_correct == 3
