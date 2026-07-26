"""Tests for Step 8 progress reads and dashboard summary."""

from decimal import Decimal

from backend.models.progress import Progress


def _auth_headers(client, username: str = "progress_user") -> dict[str, str]:
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


def test_progress_summary_aggregates_topic_rows(client, database_session) -> None:
    """Summary totals and weak topics come from Progress rows."""

    headers = _auth_headers(client)
    # Resolve user id from /me
    user_id = client.get("/api/v1/auth/me", headers=headers).json()["id"]

    database_session.add_all(
        [
            Progress(
                user_id=user_id,
                topic="loops",
                questions_attempted=4,
                questions_correct=1,
                accuracy=Decimal("25.00"),
            ),
            Progress(
                user_id=user_id,
                topic="lists",
                questions_attempted=2,
                questions_correct=2,
                accuracy=Decimal("100.00"),
            ),
        ]
    )
    database_session.commit()

    summary = client.get("/api/v1/progress/summary", headers=headers).json()
    assert summary["questions_attempted"] == 6
    assert summary["questions_correct"] == 3
    assert summary["overall_accuracy"] == "50.00"
    assert summary["weak_topics"] == ["loops"]

    rows = client.get("/api/v1/progress", headers=headers).json()
    assert [row["topic"] for row in rows] == ["lists", "loops"]


def test_progress_is_user_scoped(client, database_session) -> None:
    """Students only see their own progress rows."""

    headers_a = _auth_headers(client, "alice_progress")
    headers_b = _auth_headers(client, "bob_progress")
    alice_id = client.get("/api/v1/auth/me", headers=headers_a).json()["id"]

    database_session.add(
        Progress(
            user_id=alice_id,
            topic="operators",
            questions_attempted=1,
            questions_correct=1,
            accuracy=Decimal("100.00"),
        )
    )
    database_session.commit()

    assert client.get("/api/v1/progress", headers=headers_a).json()[0]["topic"] == (
        "operators"
    )
    assert client.get("/api/v1/progress", headers=headers_b).json() == []
