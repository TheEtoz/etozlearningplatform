"""Versioned student-submission API routes."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.dependencies import get_current_user
from backend.models.user import User
from backend.schemas.submission import (
    SubmissionCreate,
    SubmissionResponse,
    submission_to_response,
)
from backend.services.class_service import (
    ClassServiceError,
    get_classroom_for_access,
    question_published_in_class,
)
from backend.services.question_service import get_question
from backend.services.submission_service import (
    SubmissionError,
    create_submission,
    list_user_submissions,
)

router = APIRouter(prefix="/submissions", tags=["Submissions"])


@router.get("", response_model=list[SubmissionResponse])
def list_my_submissions(
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> list[SubmissionResponse]:
    """Return the authenticated student's newest submissions."""

    submissions = list_user_submissions(database, user_id=current_user.id)
    return [submission_to_response(item) for item in submissions]


@router.post("", response_model=SubmissionResponse)
def create_submission_route(
    payload: SubmissionCreate,
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> SubmissionResponse:
    """Grade an MCQ or coding attempt, persist it, and update progress."""

    if payload.class_id is not None:
        try:
            get_classroom_for_access(
                database, payload.class_id, user_id=current_user.id
            )
        except ClassServiceError as error:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(error),
            ) from error
        if not question_published_in_class(
            database,
            class_id=payload.class_id,
            question_id=payload.question_id,
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Question is not part of this class",
            )
    else:
        # Global submissions only allowed for public/legacy bank items.
        question = get_question(database, payload.question_id)
        if question is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Question not found",
            )
        if (
            question.visibility == "private"
            and question.owner_id not in (None, current_user.id)
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Private question — submit inside an enrolled class",
            )

    try:
        submission, feedback = create_submission(
            database,
            user_id=current_user.id,
            question_id=payload.question_id,
            answer=payload.answer,
            code=payload.code,
            class_id=payload.class_id,
        )
    except SubmissionError as error:
        message = str(error)
        status_code = (
            status.HTTP_404_NOT_FOUND
            if message == "Question not found"
            else status.HTTP_400_BAD_REQUEST
        )
        # Docker setup problems should surface as 503, not student input errors.
        if "Docker" in message or "docker" in message:
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        raise HTTPException(status_code=status_code, detail=message) from error

    return submission_to_response(submission, feedback)
