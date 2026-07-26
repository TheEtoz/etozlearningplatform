"""Validated API schemas for MCQ and coding submissions."""

from datetime import datetime
from enum import Enum
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SubmissionStatus(str, Enum):
    """Possible outcomes of a student attempt."""

    PENDING = "pending"
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"


class SubmissionCreate(BaseModel):
    """Student input for one question attempt."""

    question_id: int = Field(gt=0)
    answer: str | None = Field(default=None, max_length=10_000)
    code: str | None = Field(default=None, max_length=50_000)

    @model_validator(mode="after")
    def require_exactly_one_response(self) -> Self:
        """Accept an MCQ answer or source code, but not both."""

        has_answer = bool(self.answer and self.answer.strip())
        has_code = bool(self.code and self.code.strip())
        if has_answer == has_code:
            raise ValueError("Provide exactly one of answer or code")
        return self


class TestCaseResult(BaseModel):
    """One hidden-test outcome returned after a coding submission."""

    index: int
    passed: bool
    stdin: str | None = None
    expected_stdout: str | None = None
    actual_stdout: str | None = None
    stderr: str | None = None
    timed_out: bool = False
    exit_code: int | None = None


class SubmissionResponse(BaseModel):
    """A saved submission returned to its owner.

    Coding attempts may also include ephemeral Docker feedback that is not
    stored as separate database columns.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    question_id: int
    answer: str | None
    code: str | None
    score: int = Field(ge=0, le=100)
    status: SubmissionStatus
    created_at: datetime
    stdout: str | None = None
    stderr: str | None = None
    timed_out: bool = False
    tests_passed: int | None = None
    tests_total: int | None = None
    test_results: list[TestCaseResult] | None = None


class CodeRunRequest(BaseModel):
    """Free-run request that executes code without saving a submission."""

    code: str = Field(min_length=1, max_length=50_000)


class CodeRunResponse(BaseModel):
    """Stdout/stderr captured from a sandbox free-run."""

    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool
    detail: str | None = None


def submission_to_response(
    submission: Any,
    feedback: dict[str, Any] | None = None,
) -> SubmissionResponse:
    """Merge a persisted submission with optional Docker feedback."""

    payload = {
        "id": submission.id,
        "question_id": submission.question_id,
        "answer": submission.answer,
        "code": submission.code,
        "score": submission.score,
        "status": submission.status,
        "created_at": submission.created_at,
    }
    if feedback:
        payload.update(feedback)
    return SubmissionResponse.model_validate(payload)
