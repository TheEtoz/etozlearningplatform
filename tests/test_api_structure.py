"""Tests for Step 4 schemas, route structure, authentication, and CORS."""

import pytest
from pydantic import ValidationError

from backend.schemas.question import QuestionCreate
from backend.schemas.submission import SubmissionCreate


def _auth_headers(client) -> dict[str, str]:
    """Create a test user and return a Bearer authorization header."""

    client.post(
        "/api/v1/auth/register",
        json={
            "username": "route_tester",
            "email": "routes@example.com",
            "password": "password123",
        },
    )
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "route_tester", "password": "password123"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_openapi_contains_all_versioned_route_groups(client) -> None:
    """The generated API contract should expose each Step 4 route group."""

    paths = client.get("/openapi.json").json()["paths"]

    assert {
        "/api/v1/auth/register",
        "/api/v1/auth/login",
        "/api/v1/auth/me",
        "/api/v1/quizzes",
        "/api/v1/quizzes/{quiz_id}/questions",
        "/api/v1/quizzes/{quiz_id}/complete",
        "/api/v1/questions",
        "/api/v1/topics",
        "/api/v1/path",
        "/api/v1/code/run",
        "/api/v1/submissions",
        "/api/v1/progress",
        "/api/v1/progress/summary",
        "/api/v1/admin/questions",
        "/api/v1/admin/quizzes",
        "/api/v1/admin/modules",
    }.issubset(paths)


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/questions",
        "/api/v1/submissions",
        "/api/v1/progress",
        "/api/v1/progress/summary",
    ],
)
def test_feature_routes_require_authentication(client, path: str) -> None:
    """Student data routes must reject anonymous requests."""

    response = client.get(path)

    assert response.status_code == 401


def test_authenticated_placeholder_routes_return_typed_responses(client) -> None:
    """Authenticated routes should return their documented Step 4 shapes."""

    headers = _auth_headers(client)

    assert client.get("/api/v1/questions", headers=headers).json() == []
    assert client.get("/api/v1/submissions", headers=headers).json() == []
    assert client.get("/api/v1/progress", headers=headers).json() == []
    assert client.get("/api/v1/progress/summary", headers=headers).json() == {
        "questions_attempted": 0,
        "questions_correct": 0,
        "overall_accuracy": "0.00",
        "weak_topics": [],
    }


def test_invalid_submission_body_returns_422(client) -> None:
    """FastAPI should reject malformed submissions before business logic."""

    headers = _auth_headers(client)
    response = client.post(
        "/api/v1/submissions",
        headers=headers,
        json={"question_id": 0, "answer": "", "code": ""},
    )

    assert response.status_code == 422
    assert response.json()["detail"]


def test_cors_preflight_allows_streamlit_origin(client) -> None:
    """The local Streamlit frontend should pass browser CORS checks."""

    response = client.options(
        "/api/v1/questions",
        headers={
            "Origin": "http://localhost:8501",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == (
        "http://localhost:8501"
    )
    assert "authorization" in response.headers[
        "access-control-allow-headers"
    ].lower()


def test_mcq_schema_requires_valid_choices_and_answer() -> None:
    """MCQ validation should reject an answer absent from its choices."""

    with pytest.raises(ValidationError, match="correct_answer"):
        QuestionCreate(
            title="Python addition",
            description="What does 2 + 3 return?",
            difficulty="easy",
            type="mcq",
            topics=["operators"],
            choices=["4", "5"],
            correct_answer="6",
        )


def test_coding_schema_requires_test_cases() -> None:
    """Coding questions need hidden tests before they can be saved."""

    with pytest.raises(ValidationError, match="test case"):
        QuestionCreate(
            title="Add two numbers",
            description="Write a function that adds two integers.",
            difficulty="easy",
            type="coding",
            topics=["functions"],
            starter_code="def add(a, b):\n    pass",
        )


def test_question_schema_requires_at_least_one_topic() -> None:
    with pytest.raises(ValidationError):
        QuestionCreate(
            title="No topics",
            description="Should fail",
            difficulty="easy",
            type="mcq",
            topics=[],
            choices=["A", "B"],
            correct_answer="A",
        )


def test_submission_schema_requires_exactly_one_response() -> None:
    """A submission cannot contain both an MCQ answer and source code."""

    with pytest.raises(ValidationError, match="exactly one"):
        SubmissionCreate(
            question_id=1,
            answer="B",
            code="print('B')",
        )
