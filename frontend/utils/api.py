"""HTTP helpers for talking to the FastAPI backend from Streamlit."""

import os

import requests
from dotenv import load_dotenv
from requests.exceptions import ConnectionError, ReadTimeout, RequestException, Timeout

from frontend.utils.public_mode import _setting, is_public_mode

load_dotenv()

DEFAULT_BACKEND_URL = "http://127.0.0.1:8000"
PRODUCTION_BACKEND_URL = "https://etoz-api.onrender.com"


def _looks_like_streamlit_cloud() -> bool:
    """Heuristic: Streamlit Community Cloud mount / sharing env."""

    if os.getenv("STREAMLIT_SHARING_MODE") or os.getenv("STREAMLIT_SERVER_HEADLESS"):
        if os.path.exists("/mount/src") or os.path.exists("/app"):
            return True
    return os.path.exists("/mount/src")


def _resolve_backend_url() -> str:
    configured = _setting("BACKEND_URL", "").rstrip("/")
    if configured:
        return configured
    if _looks_like_streamlit_cloud():
        return PRODUCTION_BACKEND_URL
    return DEFAULT_BACKEND_URL


BACKEND_URL = _resolve_backend_url()
API_BASE_URL = f"{BACKEND_URL}/api/v1"
REQUEST_TIMEOUT_SECONDS = 15
# Coding runs wait for Docker; allow more than the sandbox timeout.
CODE_REQUEST_TIMEOUT_SECONDS = 45


def _auth_headers(access_token: str | None) -> dict[str, str]:
    if not access_token:
        return {}
    return {"Authorization": f"Bearer {access_token}"}


def _use_guest_api(access_token: str | None) -> bool:
    """Use no-auth public routes only for anonymous visitors in public mode."""

    return is_public_mode() and not access_token


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
    """Create a new account (unverified until email link is used)."""

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


def verify_email(token: str) -> dict:
    response = _request(
        "POST",
        f"{API_BASE_URL}/auth/verify-email",
        json={"token": token},
    )
    if not response.ok:
        raise APIError(_extract_error_message(response), response.status_code)
    return response.json()


def resend_verification(email: str) -> dict:
    response = _request(
        "POST",
        f"{API_BASE_URL}/auth/resend-verification",
        json={"email": email},
    )
    if not response.ok:
        raise APIError(_extract_error_message(response), response.status_code)
    return response.json()


def forgot_password(email: str) -> dict:
    response = _request(
        "POST",
        f"{API_BASE_URL}/auth/forgot-password",
        json={"email": email},
    )
    if not response.ok:
        raise APIError(_extract_error_message(response), response.status_code)
    return response.json()


def reset_password(token: str, new_password: str) -> dict:
    response = _request(
        "POST",
        f"{API_BASE_URL}/auth/reset-password",
        json={"token": token, "new_password": new_password},
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
    """Legacy global quiz list (always empty; use class quizzes)."""

    response = _request(
        "GET",
        f"{API_BASE_URL}/quizzes",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    if not response.ok:
        raise APIError(_extract_error_message(response), response.status_code)
    return response.json()


def list_class_quizzes(access_token: str | None, class_id: int) -> list[dict]:
    """Fetch published quiz cards for one enrolled (or public) class."""

    if _use_guest_api(access_token):
        url = f"{API_BASE_URL}/public/classes/{class_id}/quizzes"
        headers: dict[str, str] = {}
    else:
        url = f"{API_BASE_URL}/classes/{class_id}/quizzes"
        headers = _auth_headers(access_token)
    response = _request("GET", url, headers=headers)
    if not response.ok:
        raise APIError(_extract_error_message(response), response.status_code)
    return response.json()


def get_quiz_questions(
    access_token: str | None, quiz_id: int, class_id: int
) -> list[dict]:
    """Fetch student-safe questions for one class-published quiz."""

    if _use_guest_api(access_token):
        url = (
            f"{API_BASE_URL}/public/classes/{class_id}/quizzes/{quiz_id}/questions"
        )
        headers: dict[str, str] = {}
    else:
        url = f"{API_BASE_URL}/classes/{class_id}/quizzes/{quiz_id}/questions"
        headers = _auth_headers(access_token)
    response = _request("GET", url, headers=headers)
    if not response.ok:
        raise APIError(_extract_error_message(response), response.status_code)
    return response.json()


def complete_quiz(
    access_token: str | None,
    quiz_id: int,
    answers: list[dict],
    class_id: int,
) -> dict:
    """Finish a class-scoped quiz and receive score plus review."""

    if _use_guest_api(access_token):
        url = (
            f"{API_BASE_URL}/public/classes/{class_id}/quizzes/{quiz_id}/complete"
        )
        headers: dict[str, str] = {}
    else:
        url = f"{API_BASE_URL}/classes/{class_id}/quizzes/{quiz_id}/complete"
        headers = _auth_headers(access_token)
    response = _request(
        "POST",
        url,
        headers=headers,
        json={"answers": answers},
        timeout=CODE_REQUEST_TIMEOUT_SECONDS,
    )
    if not response.ok:
        raise APIError(_extract_error_message(response), response.status_code)
    return response.json()


def get_coding_path(access_token: str | None, class_id: int) -> list[dict]:
    """Fetch the free-jump coding path for one class."""

    if _use_guest_api(access_token):
        url = f"{API_BASE_URL}/public/classes/{class_id}/path"
        headers: dict[str, str] = {}
    else:
        url = f"{API_BASE_URL}/classes/{class_id}/path"
        headers = _auth_headers(access_token)
    response = _request("GET", url, headers=headers)
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


def create_topic(
    access_token: str,
    name: str,
    *,
    subject: str = "python",
) -> dict:
    """Create an area inside a subject from the teacher UI."""

    response = _request(
        "POST",
        f"{API_BASE_URL}/admin/topics",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"name": name, "subject": subject},
    )
    if not response.ok:
        raise APIError(_extract_error_message(response), response.status_code)
    return response.json()


def list_subjects(access_token: str) -> list[dict]:
    """Fetch subjects with nested areas."""

    response = _request(
        "GET",
        f"{API_BASE_URL}/admin/subjects",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    if not response.ok:
        raise APIError(_extract_error_message(response), response.status_code)
    return response.json()


def create_subject(access_token: str, name: str) -> dict:
    response = _request(
        "POST",
        f"{API_BASE_URL}/admin/subjects",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"name": name},
    )
    if not response.ok:
        raise APIError(_extract_error_message(response), response.status_code)
    return response.json()


def clone_question(access_token: str, question_id: int) -> dict:
    """Copy a bank question for quiz-local customization."""

    response = _request(
        "POST",
        f"{API_BASE_URL}/admin/questions/{question_id}/clone",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    if not response.ok:
        raise APIError(_extract_error_message(response), response.status_code)
    return response.json()


def run_code(access_token: str | None, code: str) -> dict:
    """Execute Python in the Docker sandbox without grading or saving."""

    if _use_guest_api(access_token):
        url = f"{API_BASE_URL}/public/code/run"
        headers: dict[str, str] = {}
    else:
        url = f"{API_BASE_URL}/code/run"
        headers = _auth_headers(access_token)
    response = _request(
        "POST",
        url,
        headers=headers,
        json={"code": code},
        timeout=CODE_REQUEST_TIMEOUT_SECONDS,
    )
    if not response.ok:
        raise APIError(_extract_error_message(response), response.status_code)
    return response.json()


def submit_code(
    access_token: str | None,
    question_id: int,
    code: str,
    class_id: int | None = None,
) -> dict:
    """Grade coding against hidden tests (persists only when not in public mode)."""

    payload: dict = {"question_id": question_id, "code": code}
    if class_id is not None:
        payload["class_id"] = class_id
    if _use_guest_api(access_token):
        url = f"{API_BASE_URL}/public/submissions/grade"
        headers: dict[str, str] = {}
    else:
        url = f"{API_BASE_URL}/submissions"
        headers = _auth_headers(access_token)
    response = _request(
        "POST",
        url,
        headers=headers,
        json=payload,
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


def clone_quiz(access_token: str, quiz_id: int) -> dict:
    """Deep-copy a quiz (and its questions) for class use."""

    response = _request(
        "POST",
        f"{API_BASE_URL}/admin/quizzes/{quiz_id}/clone",
        headers={"Authorization": f"Bearer {access_token}"},
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


def list_admin_modules(
    access_token: str,
    *,
    class_id: int | None = None,
) -> list[dict]:
    params = {}
    if class_id is not None:
        params["class_id"] = class_id
    response = _request(
        "GET",
        f"{API_BASE_URL}/admin/modules",
        headers={"Authorization": f"Bearer {access_token}"},
        params=params or None,
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


def set_module_blocks(
    access_token: str,
    module_id: int,
    blocks: list[dict],
) -> dict:
    response = _request(
        "PUT",
        f"{API_BASE_URL}/admin/modules/{module_id}/blocks",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"blocks": blocks},
    )
    if not response.ok:
        raise APIError(_extract_error_message(response), response.status_code)
    return response.json()

def get_admin_module(access_token: str, module_id: int) -> dict:
    response = _request(
        "GET",
        f"{API_BASE_URL}/admin/modules/{module_id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    if not response.ok:
        raise APIError(_extract_error_message(response), response.status_code)
    return response.json()


def check_mcq_answer(
    access_token: str | None, question_id: int, answer: str
) -> dict:
    if _use_guest_api(access_token):
        url = f"{API_BASE_URL}/public/questions/{question_id}/check"
        headers: dict[str, str] = {}
    else:
        url = f"{API_BASE_URL}/questions/{question_id}/check"
        headers = _auth_headers(access_token)
    response = _request(
        "POST",
        url,
        headers=headers,
        json={"answer": answer},
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


def list_media_library(access_token: str) -> list[dict]:
    """List uploaded media files for teacher reuse."""

    response = _request(
        "GET",
        f"{API_BASE_URL}/admin/media",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    if not response.ok:
        raise APIError(_extract_error_message(response), response.status_code)
    return response.json()


def upload_media(access_token: str, filename: str, content: bytes, content_type: str | None = None) -> dict:
    """Upload a file into the backend media/ library."""

    response = _request(
        "POST",
        f"{API_BASE_URL}/admin/media/upload",
        headers={"Authorization": f"Bearer {access_token}"},
        files={
            "file": (filename, content, content_type or "application/octet-stream"),
        },
        timeout=CODE_REQUEST_TIMEOUT_SECONDS,
    )
    if not response.ok:
        raise APIError(_extract_error_message(response), response.status_code)
    return response.json()


def media_link_snippet(
    access_token: str,
    url: str,
    *,
    label: str | None = None,
) -> dict:
    """Turn a URL into a LaTeX href / YouTube / media snippet."""

    payload: dict = {"url": url}
    if label:
        payload["label"] = label
    response = _request(
        "POST",
        f"{API_BASE_URL}/admin/media/link",
        headers={"Authorization": f"Bearer {access_token}"},
        json=payload,
    )
    if not response.ok:
        raise APIError(_extract_error_message(response), response.status_code)
    return response.json()


def list_my_classes(access_token: str) -> list[dict]:
    response = _request(
        "GET",
        f"{API_BASE_URL}/classes/mine",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    if not response.ok:
        raise APIError(_extract_error_message(response), response.status_code)
    return response.json()


def list_enrolled_classes(access_token: str) -> list[dict]:
    response = _request(
        "GET",
        f"{API_BASE_URL}/classes/enrolled",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    if not response.ok:
        raise APIError(_extract_error_message(response), response.status_code)
    return response.json()


def list_public_classes(access_token: str | None = None) -> list[dict]:
    if _use_guest_api(access_token):
        url = f"{API_BASE_URL}/public/classes"
        headers: dict[str, str] = {}
    else:
        url = f"{API_BASE_URL}/classes/public"
        headers = _auth_headers(access_token)
    response = _request("GET", url, headers=headers)
    if not response.ok:
        raise APIError(_extract_error_message(response), response.status_code)
    return response.json()


def get_demo_class() -> dict:
    """Return the preferred public class for the homepage."""

    response = _request("GET", f"{API_BASE_URL}/public/demo-class")
    if not response.ok:
        raise APIError(_extract_error_message(response), response.status_code)
    return response.json()


def get_class(access_token: str | None, class_id: int) -> dict:
    if _use_guest_api(access_token):
        url = f"{API_BASE_URL}/public/classes/{class_id}"
        headers: dict[str, str] = {}
    else:
        url = f"{API_BASE_URL}/classes/{class_id}"
        headers = _auth_headers(access_token)
    response = _request("GET", url, headers=headers)
    if not response.ok:
        raise APIError(_extract_error_message(response), response.status_code)
    return response.json()


def create_class(access_token: str, payload: dict) -> dict:
    response = _request(
        "POST",
        f"{API_BASE_URL}/classes",
        headers={"Authorization": f"Bearer {access_token}"},
        json=payload,
    )
    if not response.ok:
        raise APIError(_extract_error_message(response), response.status_code)
    return response.json()


def update_class(access_token: str, class_id: int, payload: dict) -> dict:
    response = _request(
        "PATCH",
        f"{API_BASE_URL}/classes/{class_id}",
        headers={"Authorization": f"Bearer {access_token}"},
        json=payload,
    )
    if not response.ok:
        raise APIError(_extract_error_message(response), response.status_code)
    return response.json()


def delete_class(access_token: str, class_id: int) -> None:
    response = _request(
        "DELETE",
        f"{API_BASE_URL}/classes/{class_id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    if not response.ok:
        raise APIError(_extract_error_message(response), response.status_code)


def regenerate_class_code(access_token: str, class_id: int) -> dict:
    response = _request(
        "POST",
        f"{API_BASE_URL}/classes/{class_id}/regenerate-code",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    if not response.ok:
        raise APIError(_extract_error_message(response), response.status_code)
    return response.json()


def enroll_in_class(
    access_token: str,
    *,
    code: str | None = None,
    class_id: int | None = None,
) -> dict:
    payload: dict = {}
    if code:
        payload["code"] = code
    if class_id is not None:
        payload["class_id"] = class_id
    response = _request(
        "POST",
        f"{API_BASE_URL}/classes/enroll",
        headers={"Authorization": f"Bearer {access_token}"},
        json=payload,
    )
    if not response.ok:
        raise APIError(_extract_error_message(response), response.status_code)
    return response.json()


def set_class_quizzes(access_token: str, class_id: int, quiz_ids: list[int]) -> dict:
    response = _request(
        "PUT",
        f"{API_BASE_URL}/classes/{class_id}/quizzes",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"quiz_ids": quiz_ids},
    )
    if not response.ok:
        raise APIError(_extract_error_message(response), response.status_code)
    return response.json()


def set_class_modules(access_token: str, class_id: int, module_ids: list[int]) -> dict:
    response = _request(
        "PUT",
        f"{API_BASE_URL}/classes/{class_id}/modules",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"module_ids": module_ids},
    )
    if not response.ok:
        raise APIError(_extract_error_message(response), response.status_code)
    return response.json()


def get_class_performance(access_token: str, class_id: int) -> list[dict]:
    response = _request(
        "GET",
        f"{API_BASE_URL}/classes/{class_id}/performance",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    if not response.ok:
        raise APIError(_extract_error_message(response), response.status_code)
    return response.json()


def list_class_announcements(
    access_token: str | None, class_id: int
) -> list[dict]:
    if _use_guest_api(access_token):
        url = f"{API_BASE_URL}/public/classes/{class_id}/announcements"
        headers: dict[str, str] = {}
    else:
        url = f"{API_BASE_URL}/classes/{class_id}/announcements"
        headers = _auth_headers(access_token)
    response = _request("GET", url, headers=headers)
    if not response.ok:
        raise APIError(_extract_error_message(response), response.status_code)
    return response.json()


def create_class_announcement(
    access_token: str,
    class_id: int,
    title: str,
    body: str,
) -> dict:
    response = _request(
        "POST",
        f"{API_BASE_URL}/classes/{class_id}/announcements",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"title": title, "body": body},
    )
    if not response.ok:
        raise APIError(_extract_error_message(response), response.status_code)
    return response.json()


def delete_class_announcement(
    access_token: str,
    class_id: int,
    announcement_id: int,
) -> None:
    response = _request(
        "DELETE",
        f"{API_BASE_URL}/classes/{class_id}/announcements/{announcement_id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    if not response.ok:
        raise APIError(_extract_error_message(response), response.status_code)

