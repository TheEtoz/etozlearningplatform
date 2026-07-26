"""Grade and persist MCQ / coding submissions."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.submission import Submission
from backend.services.docker_service import (
    DockerExecutionError,
    ExecutionResult,
    grade_python_code,
)
from backend.services.progress_service import record_topic_attempt
from backend.services.question_service import get_question


class SubmissionError(ValueError):
    """Raised for student-facing submission problems."""


def list_user_submissions(
    database: Session,
    *,
    user_id: int,
    limit: int = 50,
) -> list[Submission]:
    """Return the newest submissions for one student."""

    statement = (
        select(Submission)
        .where(Submission.user_id == user_id)
        .order_by(Submission.id.desc())
        .limit(limit)
    )
    return list(database.scalars(statement).all())


def _grade_mcq(question: Question, answer: str) -> tuple[int, str]:
    """Return score and status for an MCQ answer."""

    selected = answer.strip()
    correct = (question.correct_answer or "").strip()
    if selected == correct:
        return 100, "passed"
    return 0, "failed"


def _grade_coding(question: Question, code: str) -> tuple[int, str, ExecutionResult]:
    """Run hidden tests in Docker and map the report to score/status."""

    test_cases = list(question.test_cases or [])
    try:
        result = grade_python_code(code, test_cases)
    except DockerExecutionError as error:
        raise SubmissionError(str(error)) from error

    if result.timed_out or result.mode == "error":
        return 0, "error", result

    if result.tests_total == 0:
        return 0, "error", result

    score = int(round((result.tests_passed / result.tests_total) * 100))
    status = "passed" if result.tests_passed == result.tests_total else "failed"
    return score, status, result


def create_submission(
    database: Session,
    *,
    user_id: int,
    question_id: int,
    answer: str | None,
    code: str | None,
) -> tuple[Submission, dict[str, Any]]:
    """Validate, grade, persist, and update topic progress for one attempt."""

    question = get_question(database, question_id)
    if question is None:
        raise SubmissionError("Question not found")

    feedback: dict[str, Any] = {
        "stdout": None,
        "stderr": None,
        "timed_out": False,
        "tests_passed": None,
        "tests_total": None,
        "test_results": None,
    }

    if question.type == "mcq":
        if not answer or not answer.strip():
            raise SubmissionError("MCQ questions require an answer")
        if code and code.strip():
            raise SubmissionError("MCQ questions do not accept code")
        score, status = _grade_mcq(question, answer)
        submission = Submission(
            user_id=user_id,
            question_id=question.id,
            answer=answer.strip(),
            code=None,
            score=score,
            status=status,
        )
    elif question.type == "coding":
        if not code or not code.strip():
            raise SubmissionError("Coding questions require source code")
        if answer and answer.strip():
            raise SubmissionError("Coding questions do not accept MCQ answers")
        if (question.language or "python").lower() != "python":
            raise SubmissionError("Only Python coding questions are supported")
        score, status, result = _grade_coding(question, code)
        submission = Submission(
            user_id=user_id,
            question_id=question.id,
            answer=None,
            code=code,
            score=score,
            status=status,
        )
        feedback = {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "timed_out": result.timed_out,
            "tests_passed": result.tests_passed,
            "tests_total": result.tests_total,
            "test_results": result.test_results,
        }
    else:
        raise SubmissionError(f"Unsupported question type: {question.type}")

    database.add(submission)
    topic_names = question.topics or (
        [question.topic] if question.topic else ["general"]
    )
    for topic_name in topic_names:
        record_topic_attempt(
            database,
            user_id=user_id,
            topic=topic_name,
            questions_attempted=1,
            questions_correct=1 if status == "passed" else 0,
        )
    database.commit()
    database.refresh(submission)
    return submission, feedback
