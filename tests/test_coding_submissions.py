"""Tests for Step 7 coding execution and submission grading."""

from unittest.mock import patch

from backend.models.progress import Progress
from backend.models.question import Question
from backend.models.submission import Submission
from backend.services.docker_service import ExecutionResult


def _auth_headers(client) -> dict[str, str]:
    """Create a test user and return a Bearer authorization header."""

    client.post(
        "/api/v1/auth/register",
        json={
            "username": "coder",
            "email": "coder@example.com",
            "password": "password123",
        },
    )
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "coder", "password": "password123"},
    )
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _seed_coding_question(database_session) -> Question:
    """Insert one Python coding exercise with hidden tests."""

    question = Question(
        title="Hello, World!",
        description="Print Hello, World!",
        difficulty="easy",
        type="coding",
        topic="basics",
        language="python",
        starter_code='print("Hello, World!")\n',
        test_cases=[{"stdin": "", "expected_stdout": "Hello, World!"}],
    )
    database_session.add(question)
    database_session.commit()
    database_session.refresh(question)
    return question


def test_openapi_includes_code_run_route(client) -> None:
    """The free-run endpoint should appear in the OpenAPI contract."""

    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/v1/code/run" in paths


def test_code_run_requires_authentication(client) -> None:
    """Anonymous users cannot execute code."""

    response = client.post("/api/v1/code/run", json={"code": "print(1)"})
    assert response.status_code == 401


def test_code_run_returns_stdout(client) -> None:
    """Free-run should return captured stdout from the sandbox."""

    headers = _auth_headers(client)
    fake = ExecutionResult(
        mode="run",
        stdout="hello\n",
        stderr="",
        exit_code=0,
        timed_out=False,
    )

    with patch(
        "backend.routes.code.run_python_code",
        return_value=fake,
    ) as mocked:
        response = client.post(
            "/api/v1/code/run",
            headers=headers,
            json={"code": 'print("hello")'},
        )

    assert response.status_code == 200
    assert response.json()["stdout"] == "hello\n"
    assert response.json()["timed_out"] is False
    mocked.assert_called_once_with('print("hello")')


def test_coding_submission_persists_and_updates_progress(
    client,
    database_session,
) -> None:
    """A passing coding submit creates a Submission and Progress row."""

    headers = _auth_headers(client)
    question = _seed_coding_question(database_session)
    fake = ExecutionResult(
        mode="grade",
        stdout="",
        stderr="",
        exit_code=0,
        timed_out=False,
        tests_passed=1,
        tests_total=1,
        test_results=[
            {
                "index": 0,
                "passed": True,
                "stdin": "",
                "expected_stdout": "Hello, World!",
                "actual_stdout": "Hello, World!",
                "stderr": "",
                "timed_out": False,
                "exit_code": 0,
            }
        ],
    )

    with patch(
        "backend.services.submission_service.grade_python_code",
        return_value=fake,
    ):
        response = client.post(
            "/api/v1/submissions",
            headers=headers,
            json={
                "question_id": question.id,
                "code": 'print("Hello, World!")',
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "passed"
    assert payload["score"] == 100
    assert payload["tests_passed"] == 1
    assert payload["tests_total"] == 1

    submissions = database_session.query(Submission).all()
    assert len(submissions) == 1
    assert submissions[0].status == "passed"

    progress = database_session.query(Progress).one()
    assert progress.topic == "basics"
    assert progress.questions_attempted == 1
    assert progress.questions_correct == 1


def test_coding_submission_failed_tests(client, database_session) -> None:
    """Failing hidden tests should mark the submission failed with score < 100."""

    headers = _auth_headers(client)
    question = _seed_coding_question(database_session)
    fake = ExecutionResult(
        mode="grade",
        exit_code=1,
        tests_passed=0,
        tests_total=1,
        test_results=[
            {
                "index": 0,
                "passed": False,
                "stdin": "",
                "expected_stdout": "Hello, World!",
                "actual_stdout": "hi",
                "stderr": "",
                "timed_out": False,
                "exit_code": 0,
            }
        ],
    )

    with patch(
        "backend.services.submission_service.grade_python_code",
        return_value=fake,
    ):
        response = client.post(
            "/api/v1/submissions",
            headers=headers,
            json={"question_id": question.id, "code": 'print("hi")'},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert response.json()["score"] == 0


def test_mcq_submission_via_submissions_endpoint(
    client,
    database_session,
) -> None:
    """POST /submissions also grades MCQ answers without Docker."""

    headers = _auth_headers(client)
    question = Question(
        title="MCQ via submissions",
        description="2 + 2?",
        difficulty="easy",
        type="mcq",
        topic="operators",
        language="python",
        choices=["3", "4"],
        correct_answer="4",
    )
    database_session.add(question)
    database_session.commit()
    database_session.refresh(question)

    response = client.post(
        "/api/v1/submissions",
        headers=headers,
        json={"question_id": question.id, "answer": "4"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "passed"
    assert response.json()["score"] == 100


def test_list_submissions_returns_own_attempts(
    client,
    database_session,
) -> None:
    """GET /submissions should list persisted attempts for the current user."""

    headers = _auth_headers(client)
    question = Question(
        title="List submissions MCQ",
        description="1+1?",
        difficulty="easy",
        type="mcq",
        topic="operators",
        language="python",
        choices=["1", "2"],
        correct_answer="2",
    )
    database_session.add(question)
    database_session.commit()
    database_session.refresh(question)

    client.post(
        "/api/v1/submissions",
        headers=headers,
        json={"question_id": question.id, "answer": "2"},
    )

    response = client.get("/api/v1/submissions", headers=headers)
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["question_id"] == question.id
