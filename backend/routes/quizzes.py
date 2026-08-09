"""Legacy student quiz routes — catalog is class-scoped."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.dependencies import get_current_user
from backend.models.user import User
from backend.schemas.quiz import QuizCardResponse

router = APIRouter(prefix="/quizzes", tags=["Quizzes"])


@router.get("", response_model=list[QuizCardResponse])
def read_quizzes(
    _: User = Depends(get_current_user),
    __: Session = Depends(get_db),
) -> list[QuizCardResponse]:
    """Global quiz catalog is disabled — students use class quizzes."""

    return []


@router.get("/{quiz_id}/questions")
def read_quiz_questions_legacy(
    quiz_id: int,
    _: User = Depends(get_current_user),
) -> None:
    """Point clients at class-scoped quiz question routes."""

    del quiz_id
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail=(
            "Quizzes are class-scoped. Use "
            "GET /api/v1/classes/{class_id}/quizzes/{quiz_id}/questions"
        ),
    )


@router.post("/{quiz_id}/complete")
def finish_quiz_legacy(
    quiz_id: int,
    _: User = Depends(get_current_user),
) -> None:
    """Point clients at class-scoped quiz completion."""

    del quiz_id
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail=(
            "Quizzes are class-scoped. Use "
            "POST /api/v1/classes/{class_id}/quizzes/{quiz_id}/complete"
        ),
    )
