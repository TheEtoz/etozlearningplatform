"""Student question-library routes (read + MCQ check)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.dependencies import get_current_user
from backend.models.user import User
from backend.schemas.question import (
    AnswerCheckRequest,
    AnswerCheckResponse,
    Difficulty,
    QuestionResponse,
    QuestionType,
)
from backend.services.class_service import user_can_access_published_question
from backend.services.question_service import (
    check_mcq_answer,
    get_question,
    list_questions as query_questions,
    question_to_student_dict,
)

router = APIRouter(prefix="/questions", tags=["Questions"])


def _student_accessible_question(
    database: Session,
    question_id: int,
    *,
    user_id: int,
):
    """Public/legacy questions, or private ones published in a class the user can access."""

    question = get_question(database, question_id)
    if question is None:
        return None
    if question.visibility != "private" or question.owner_id in (None, user_id):
        return question
    if user_can_access_published_question(
        database, user_id=user_id, question_id=question_id
    ):
        return question
    return None


@router.get("", response_model=list[QuestionResponse])
def list_questions(
    topic: Annotated[str | None, Query(min_length=2, max_length=100)] = None,
    difficulty: Difficulty | None = None,
    question_type: Annotated[QuestionType | None, Query(alias="type")] = None,
    search: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    _: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> list[dict]:
    """Return student-safe bank questions with optional filters."""

    questions = query_questions(
        database,
        topic=topic,
        difficulty=difficulty.value if difficulty else None,
        question_type=question_type.value if question_type else None,
        search=search,
        visibility="public",
        offset=offset,
        limit=limit,
    )
    return [question_to_student_dict(item) for item in questions]


@router.get("/{question_id}", response_model=QuestionResponse)
def read_question(
    question_id: int,
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> dict:
    """Return one student-safe question."""

    question = _student_accessible_question(
        database, question_id, user_id=current_user.id
    )
    if question is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found",
        )
    return question_to_student_dict(question)


@router.post(
    "/{question_id}/check",
    response_model=AnswerCheckResponse,
)
def check_question_answer(
    question_id: int,
    payload: AnswerCheckRequest,
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> AnswerCheckResponse:
    """Reveal the correct MCQ answer after an attempt."""

    question = _student_accessible_question(
        database, question_id, user_id=current_user.id
    )
    if question is None or question.type != "mcq":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="MCQ question not found",
        )
    feedback = check_mcq_answer(database, question_id, payload.answer)
    if feedback is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="MCQ question not found",
        )
    return AnswerCheckResponse(**feedback)
