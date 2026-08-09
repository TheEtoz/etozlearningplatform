"""Tests for question bank filtering and student-safe responses."""

from tests.helpers import make_question, register_and_login_headers


def _auth_headers(client, database_session) -> dict[str, str]:
    return register_and_login_headers(
        client,
        database_session,
        "question_tester",
        email="questions@example.com",
    )


def test_questions_can_be_filtered_without_exposing_answers(
    client,
    database_session,
) -> None:
    make_question(
        database_session,
        title="List indexing",
        description="Read the first list item.",
        topics=["lists"],
        choices=["0", "1"],
        correct_answer="0",
    )
    make_question(
        database_session,
        title="Loop count",
        description="Count range iterations.",
        difficulty="medium",
        topics=["loops"],
        choices=["2", "3"],
        correct_answer="3",
    )
    database_session.commit()

    response = client.get(
        "/api/v1/questions",
        params={"topic": "lists", "type": "mcq"},
        headers=_auth_headers(client, database_session),
    )

    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["title"] == "List indexing"
    assert response.json()[0]["topics"] == ["lists"]
    assert "correct_answer" not in response.json()[0]
    assert "test_cases" not in response.json()[0]


def test_question_search_and_pagination_are_validated(
    client,
    database_session,
) -> None:
    make_question(
        database_session,
        title="Dictionary lookup",
        description="Read a value by key.",
        topics=["dictionaries"],
        choices=["key", "value"],
        correct_answer="value",
    )
    database_session.commit()
    headers = _auth_headers(client, database_session)

    search_response = client.get(
        "/api/v1/questions",
        params={"search": "dictionary"},
        headers=headers,
    )
    invalid_limit = client.get(
        "/api/v1/questions",
        params={"limit": 101},
        headers=headers,
    )

    assert search_response.status_code == 200
    assert len(search_response.json()) == 1
    assert invalid_limit.status_code == 422


def test_check_answer_reveals_correct_answer_after_attempt(
    client,
    database_session,
) -> None:
    question = make_question(
        database_session,
        title="Adding integers",
        description="What is 2 + 3?",
        topics=["operators"],
        choices=["4", "5"],
        correct_answer="5",
    )
    database_session.commit()
    headers = _auth_headers(client, database_session)

    wrong = client.post(
        f"/api/v1/questions/{question.id}/check",
        headers=headers,
        json={"answer": "4"},
    )
    right = client.post(
        f"/api/v1/questions/{question.id}/check",
        headers=headers,
        json={"answer": "5"},
    )
    listed = client.get("/api/v1/questions", headers=headers)

    assert wrong.status_code == 200
    assert wrong.json()["is_correct"] is False
    assert wrong.json()["correct_answer"] == "5"
    assert right.json()["is_correct"] is True
    assert "correct_answer" not in listed.json()[0]
