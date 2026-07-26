"""HTTP helpers for talking to the FastAPI backend from Streamlit."""

import os

import requests
from dotenv import load_dotenv
from requests.exceptions import ConnectionError, ReadTimeout, RequestException, Timeout

load_dotenv()

DEFAULT_BACKEND_URL = "http://127.0.0.1:8000"
BACKEND_URL = os.getenv("BACKEND_URL", DEFAULT_BACKEND_URL).rstrip("/")
API_BASE_URL = f"{BACKEND_URL}/api/v1"
REQUEST_TIMEOUT_SECONDS = 15
# Coding runs wait for Docker; allow more than the sandbox timeout.
CODE_REQUEST_TIMEOUT_SECONDS = 45


class APIError(Exception):
    """Raised when the backend returns an error response."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def _extract_error_message(response: requests.Response) -> str:
    """Return a readable error message from a FastAPI error response."""

    try:
        payload = response.json()
    except ValueError:
        return response.text or "Unexpected API error"

    detail = payload.get("detail")
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list) and detail:
        first_error = detail[0]
        if isinstance(first_error, dict):
            return first_error.get("msg", "Validation error")
    return "Unexpected API error"


def _request(method: str, url: str, **kwargs) -> requests.Response:
    """Send an HTTP request and convert network failures into ``APIError``."""

    try:
        return requests.request(
            method,
            url,
            timeout=kwargs.pop("timeout", REQUEST_TIMEOUT_SECONDS),
            **kwargs,
        )
    except ReadTimeout as error:
        raise APIError(
            "The backend took too long to respond. "
            "Stop any old backend processes on port 8000, then restart with: "
            "python run_backend.py"
        ) from error
    except (ConnectionError, Timeout) as error:
        raise APIError(
            f"Cannot connect to the backend at {BACKEND_URL}. "
            "Start it in another terminal with: python run_backend.py"
        ) from error
    except RequestException as error:
        raise APIError(f"Network error while calling the backend: {error}") from error


def check_backend_health() -> bool:
    """Return True when the backend health endpoint responds."""

    try:
        response = _request("GET", f"{BACKEND_URL}/health")
        return response.ok
    except APIError:
        return False


def register_user(username: str, email: str, password: str) -> dict:
    """Create a new account."""

    response = _request(
        "POST",
        f"{API_BASE_URL}/auth/register",
        json={"username": username, "email": email, "password": password},
    )
    if not response.ok:
        raise APIError(_extract_error_message(response), response.status_code)
    return response.json()


def login_user(username: str, password: str) -> dict:
    """Log in and receive a JWT access token."""

    response = _request(
        "POST",
        f"{API_BASE_URL}/auth/login",
        json={"username": username, "password": password},
    )
    if not response.ok:
        raise APIError(_extract_error_message(response), response.status_code)
    return response.json()


def get_current_user(access_token: str) -> dict:
    """Fetch the profile for the logged-in user."""

    response = _request(
        "GET",
        f"{API_BASE_URL}/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    if not response.ok:
        raise APIError(_extract_error_message(response), response.status_code)
    return response.json()


def list_questions(
    access_token: str,
    *,
    topic: str | None = None,
    difficulty: str | None = None,
    question_type: str = "mcq",
    search: str | None = None,
) -> list[dict]:
    """Fetch student-safe questions using optional library filters."""

    params = {
        key: value
        for key, value in {
            "topic": topic,
            "difficulty": difficulty,
            "type": question_type,
            "search": search,
            "limit": 100,
        }.items()
        if value not in (None, "")
    }
    response = _request(
        "GET",
        f"{API_BASE_URL}/questions",
        headers={"Authorization": f"Bearer {access_token}"},
        params=params,
    )
    if not response.ok:
        raise APIError(_extract_error_message(response), response.status_code)
    return response.json()


def list_quizzes(access_token: str) -> list[dict]:
    """Fetch teacher-designed quiz cards for the practice catalog."""

    response = _request(
        "GET",
        f"{API_BASE_URL}/quizzes",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    if not response.ok:
        raise APIError(_extract_error_message(response), response.status_code)
    return response.json()


def get_quiz_questions(access_token: str, quiz_id: int) -> list[dict]:
    """Fetch student-safe questions for one quiz."""

    response = _request(
        "GET",
        f"{API_BASE_URL}/quizzes/{quiz_id}/questions",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    if not response.ok:
        raise APIError(_extract_error_message(response), response.status_code)
    return response.json()


def complete_quiz(
    access_token: str,
    quiz_id: int,
    answers: list[dict],
) -> dict:
    """Finish a mixed MCQ/coding quiz and receive score plus review."""

    response = _request(
        "POST",
        f"{API_BASE_URL}/quizzes/{quiz_id}/complete",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"answers": answers},
        timeout=CODE_REQUEST_TIMEOUT_SECONDS,
    )
    if not response.ok:
        raise APIError(_extract_error_message(response), response.status_code)
    return response.json()


def get_coding_path(access_token: str) -> list[dict]:
    """Fetch the free-jump coding path with completion flags."""

    response = _request(
        "GET",
        f"{API_BASE_URL}/path",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    if not response.ok:
        raise APIError(_extract_error_message(response), response.status_code)
    return response.json()


def list_topics(access_token: str) -> list[dict]:
    """Fetch canonical topic tags."""

    response = _request(
        "GET",
        f"{API_BASE_URL}/topics",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    if not response.ok:
        raise APIError(_extract_error_message(response), response.status_code)
    return response.json()


def create_topic(access_token: str, name: str) -> dict:
    """Create a topic area from the teacher UI."""

    response = _request(
        "POST",
        f"{API_BASE_URL}/admin/topics",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"name": name},
    )
    if not response.ok:
        raise APIError(_extract_error_message(response), response.status_code)
    return response.json()


def run_code(access_token: str, code: str) -> dict:
    """Execute Python in the Docker sandbox without grading or saving."""

    response = _request(
        "POST",
        f"{API_BASE_URL}/code/run",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"code": code},
        timeout=CODE_REQUEST_TIMEOUT_SECONDS,
    )
    if not response.ok:
        raise APIError(_extract_error_message(response), response.status_code)
    return response.json()


def submit_code(access_token: str, question_id: int, code: str) -> dict:
    """Grade coding against hidden tests and persist the submission."""

    response = _request(
        "POST",
        f"{API_BASE_URL}/submissions",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"question_id": question_id, "code": code},
        timeout=CODE_REQUEST_TIMEOUT_SECONDS,
    )
    if not response.ok:
        raise APIError(_extract_error_message(response), response.status_code)
    return response.json()


def get_progress(access_token: str) -> list[dict]:
    """Fetch per-topic progress rows for the logged-in student."""

    response = _request(
        "GET",
        f"{API_BASE_URL}/progress",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    if not response.ok:
        raise APIError(_extract_error_message(response), response.status_code)
    return response.json()


def get_progress_summary(access_token: str) -> dict:
    """Fetch dashboard summary totals and weak topics."""

    response = _request(
        "GET",
        f"{API_BASE_URL}/progress/summary",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    if not response.ok:
        raise APIError(_extract_error_message(response), response.status_code)
    return response.json()


def list_submissions(access_token: str) -> list[dict]:
    """Fetch the student's newest submissions."""

    response = _request(
        "GET",
        f"{API_BASE_URL}/submissions",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    if not response.ok:
        raise APIError(_extract_error_message(response), response.status_code)
    return response.json()


def list_admin_questions(
    access_token: str,
    *,
    topic: str | None = None,
    difficulty: str | None = None,
    question_type: str | None = None,
    search: str | None = None,
    limit: int = 1000,
) -> list[dict]:
    """Fetch full question-bank records for teachers."""

    params: dict[str, str | int] = {"limit": limit}
    if topic:
        params["topic"] = topic
    if difficulty:
        params["difficulty"] = difficulty
    if question_type:
        params["question_type"] = question_type
    if search:
        params["search"] = search
    response = _request(
        "GET",
        f"{API_BASE_URL}/admin/questions",
        headers={"Authorization": f"Bearer {access_token}"},
        params=params,
    )
    if not response.ok:
        raise APIError(_extract_error_message(response), response.status_code)
    return response.json()


def create_question(access_token: str, payload: dict) -> dict:
    """Create a bank question as a teacher."""

    response = _request(
        "POST",
        f"{API_BASE_URL}/admin/questions",
        headers={"Authorization": f"Bearer {access_token}"},
        json=payload,
    )
    if not response.ok:
        raise APIError(_extract_error_message(response), response.status_code)
    return response.json()


def update_question(access_token: str, question_id: int, payload: dict) -> dict:
    """Update a bank question as a teacher."""

    response = _request(
        "PUT",
        f"{API_BASE_URL}/admin/questions/{question_id}",
        headers={"Authorization": f"Bearer {access_token}"},
        json=payload,
    )
    if not response.ok:
        raise APIError(_extract_error_message(response), response.status_code)
    return response.json()


def delete_question(access_token: str, question_id: int) -> None:
    """Delete a bank question as a teacher."""

    response = _request(
        "DELETE",
        f"{API_BASE_URL}/admin/questions/{question_id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    if not response.ok:
        raise APIError(_extract_error_message(response), response.status_code)


def list_admin_quizzes(access_token: str) -> list[dict]:
    response = _request(
        "GET",
        f"{API_BASE_URL}/admin/quizzes",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    if not response.ok:
        raise APIError(_extract_error_message(response), response.status_code)
    return response.json()


def create_quiz(access_token: str, payload: dict) -> dict:
    response = _request(
        "POST",
        f"{API_BASE_URL}/admin/quizzes",
        headers={"Authorization": f"Bearer {access_token}"},
        json=payload,
    )
    if not response.ok:
        raise APIError(_extract_error_message(response), response.status_code)
    return response.json()


def update_quiz(access_token: str, quiz_id: int, payload: dict) -> dict:
    response = _request(
        "PUT",
        f"{API_BASE_URL}/admin/quizzes/{quiz_id}",
        headers={"Authorization": f"Bearer {access_token}"},
        json=payload,
    )
    if not response.ok:
        raise APIError(_extract_error_message(response), response.status_code)
    return response.json()


def set_quiz_questions(access_token: str, quiz_id: int, question_ids: list[int]) -> dict:
    response = _request(
        "PUT",
        f"{API_BASE_URL}/admin/quizzes/{quiz_id}/questions",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"question_ids": question_ids},
    )
    if not response.ok:
        raise APIError(_extract_error_message(response), response.status_code)
    return response.json()


def delete_quiz(access_token: str, quiz_id: int) -> None:
    response = _request(
        "DELETE",
        f"{API_BASE_URL}/admin/quizzes/{quiz_id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    if not response.ok:
        raise APIError(_extract_error_message(response), response.status_code)


def list_admin_modules(access_token: str) -> list[dict]:
    response = _request(
        "GET",
        f"{API_BASE_URL}/admin/modules",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    if not response.ok:
        raise APIError(_extract_error_message(response), response.status_code)
    return response.json()


def create_module(access_token: str, payload: dict) -> dict:
    response = _request(
        "POST",
        f"{API_BASE_URL}/admin/modules",
        headers={"Authorization": f"Bearer {access_token}"},
        json=payload,
    )
    if not response.ok:
        raise APIError(_extract_error_message(response), response.status_code)
    return response.json()


def update_module(access_token: str, module_id: int, payload: dict) -> dict:
    response = _request(
        "PUT",
        f"{API_BASE_URL}/admin/modules/{module_id}",
        headers={"Authorization": f"Bearer {access_token}"},
        json=payload,
    )
    if not response.ok:
        raise APIError(_extract_error_message(response), response.status_code)
    return response.json()


def set_module_levels(access_token: str, module_id: int, question_ids: list[int]) -> dict:
    response = _request(
        "PUT",
        f"{API_BASE_URL}/admin/modules/{module_id}/levels",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"question_ids": question_ids},
    )
    if not response.ok:
        raise APIError(_extract_error_message(response), response.status_code)
    return response.json()


def delete_module(access_token: str, module_id: int) -> None:
    response = _request(
        "DELETE",
        f"{API_BASE_URL}/admin/modules/{module_id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    if not response.ok:
        raise APIError(_extract_error_message(response), response.status_code)

