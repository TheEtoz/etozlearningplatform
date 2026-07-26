"""Student quiz catalog and mixed completion routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.dependencies import get_current_user
from backend.models.user import User
from backend.schemas.question import QuestionResponse
from backend.schemas.quiz import (
    QuizCardResponse,
    QuizCompleteRequest,
    QuizCompleteResponse,
)
from backend.services.question_service import question_to_student_dict
from backend.services.quiz_service import (
    complete_quiz,
    get_quiz,
    get_quiz_questions,
    get_student_quiz_stats,
    list_quizzes,
    quiz_topics,
)

router = APIRouter(prefix="/quizzes", tags=["Quizzes"])


@router.get("", response_model=list[QuizCardResponse])
def read_quizzes(
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> list[QuizCardResponse]:
    """Return equal-structure quiz cards with completion status."""

    stats = get_student_quiz_stats(database, current_user.id)
    cards: list[QuizCardResponse] = []
    for quiz in list_quizzes(database):
        difficulties = sorted({q.difficulty for q in quiz.questions})
        types = sorted({q.type for q in quiz.questions})
        student_stats = stats.get(quiz.id, {})
        cards.append(
            QuizCardResponse(
                id=quiz.id,
                title=quiz.title,
                description=quiz.description,
                topics=quiz_topics(quiz),
                is_timed=quiz.is_timed,
                duration_seconds=quiz.duration_seconds,
                question_count=len(quiz.questions),
                difficulties=difficulties,
                question_types=types,
                is_completed=bool(student_stats.get("is_completed", False)),
                attempt_count=int(student_stats.get("attempt_count", 0)),
                best_score=student_stats.get("best_score"),
                last_score=student_stats.get("last_score"),
            )
        )
    return cards


@router.get("/{quiz_id}/questions", response_model=list[QuestionResponse])
def read_quiz_questions(
    quiz_id: int,
    _: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> list[dict]:
    """Return student-safe questions for one quiz (MCQ and/or coding)."""

    if get_quiz(database, quiz_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quiz not found",
        )
    return [
        question_to_student_dict(item)
        for item in get_quiz_questions(database, quiz_id)
    ]


@router.post("/{quiz_id}/complete", response_model=QuizCompleteResponse)
def finish_quiz(
    quiz_id: int,
    payload: QuizCompleteRequest,
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> QuizCompleteResponse:
    """Grade mixed MCQ/coding answers and reveal results."""

    answer_map = {
        item.question_id: {"answer": item.answer, "code": item.code}
        for item in payload.answers
    }
    result = complete_quiz(
        database,
        user_id=current_user.id,
        quiz_id=quiz_id,
        answers=answer_map,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quiz not found",
        )
    return QuizCompleteResponse(**result)
