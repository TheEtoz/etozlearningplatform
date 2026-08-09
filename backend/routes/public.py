"""Unauthenticated read/play endpoints for public demo mode."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import get_db
from backend.schemas.classroom import AnnouncementResponse, ClassPublicCard, ClassResponse
from backend.schemas.path import PathModuleResponse
from backend.schemas.question import AnswerCheckRequest, AnswerCheckResponse, QuestionResponse
from backend.schemas.quiz import QuizCardResponse, QuizCompleteRequest, QuizCompleteResponse
from backend.schemas.submission import CodeRunRequest, CodeRunResponse, SubmissionCreate, SubmissionResponse
from backend.services.class_service import (
    ClassServiceError,
    build_public_class_path,
    classroom_to_dict,
    ensure_quiz_published_in_public_class,
    get_public_class_quiz_cards,
    get_public_classroom,
    list_public_announcements,
    list_public_classes,
    question_published_in_class,
    resolve_public_demo_class,
)
from backend.services.docker_service import DockerExecutionError, run_python_code
from backend.services.question_service import (
    check_mcq_answer,
    get_question,
    question_to_student_dict,
)
from backend.services.quiz_service import complete_quiz, get_quiz_questions
from backend.services.submission_service import SubmissionError, grade_without_saving

router = APIRouter(prefix="/public", tags=["Public"])


def _require_public_mode() -> None:
    if not settings.public_mode:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Public mode is disabled",
        )


def _http_error(error: ClassServiceError) -> HTTPException:
    message = str(error)
    code = status.HTTP_404_NOT_FOUND
    if "not published" in message.lower():
        code = status.HTTP_404_NOT_FOUND
    return HTTPException(status_code=code, detail=message)


@router.get("/demo-class", response_model=ClassResponse)
def read_demo_class(database: Session = Depends(get_db)) -> ClassResponse:
    """Preferred public class for the homepage."""

    _require_public_mode()
    classroom = resolve_public_demo_class(database)
    if classroom is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No public class is available",
        )
    return ClassResponse.model_validate(
        classroom_to_dict(classroom, include_code=False)
    )


@router.get("/classes", response_model=list[ClassPublicCard])
def browse_public_classes(database: Session = Depends(get_db)) -> list[ClassPublicCard]:
    _require_public_mode()
    cards: list[ClassPublicCard] = []
    for classroom in list_public_classes(database):
        data = classroom_to_dict(classroom, include_code=False)
        cards.append(
            ClassPublicCard(
                id=data["id"],
                title=data["title"],
                description=data["description"],
                owner_username=(
                    classroom.owner.username if classroom.owner else "teacher"
                ),
                quiz_count=data["quiz_count"],
                module_count=data["module_count"],
            )
        )
    return cards


@router.get("/classes/{class_id}", response_model=ClassResponse)
def read_public_class(
    class_id: int,
    database: Session = Depends(get_db),
) -> ClassResponse:
    _require_public_mode()
    try:
        classroom = get_public_classroom(database, class_id)
    except ClassServiceError as error:
        raise _http_error(error) from error
    return ClassResponse.model_validate(
        classroom_to_dict(classroom, include_code=False)
    )


@router.get(
    "/classes/{class_id}/announcements",
    response_model=list[AnnouncementResponse],
)
def read_public_announcements(
    class_id: int,
    database: Session = Depends(get_db),
) -> list[AnnouncementResponse]:
    _require_public_mode()
    try:
        rows = list_public_announcements(database, class_id)
    except ClassServiceError as error:
        raise _http_error(error) from error
    return [AnnouncementResponse.model_validate(row) for row in rows]


@router.get("/classes/{class_id}/path", response_model=list[PathModuleResponse])
def read_public_path(
    class_id: int,
    database: Session = Depends(get_db),
) -> list[dict]:
    _require_public_mode()
    try:
        return build_public_class_path(database, class_id)
    except ClassServiceError as error:
        raise _http_error(error) from error


@router.get("/classes/{class_id}/quizzes", response_model=list[QuizCardResponse])
def read_public_quizzes(
    class_id: int,
    database: Session = Depends(get_db),
) -> list[QuizCardResponse]:
    _require_public_mode()
    try:
        cards = get_public_class_quiz_cards(database, class_id)
    except ClassServiceError as error:
        raise _http_error(error) from error
    return [QuizCardResponse.model_validate(card) for card in cards]


@router.get(
    "/classes/{class_id}/quizzes/{quiz_id}/questions",
    response_model=list[QuestionResponse],
)
def read_public_quiz_questions(
    class_id: int,
    quiz_id: int,
    database: Session = Depends(get_db),
) -> list[dict]:
    _require_public_mode()
    try:
        ensure_quiz_published_in_public_class(
            database, class_id=class_id, quiz_id=quiz_id
        )
    except ClassServiceError as error:
        raise _http_error(error) from error
    return [
        question_to_student_dict(item)
        for item in get_quiz_questions(database, quiz_id)
    ]


@router.post(
    "/classes/{class_id}/quizzes/{quiz_id}/complete",
    response_model=QuizCompleteResponse,
)
def complete_public_quiz(
    class_id: int,
    quiz_id: int,
    payload: QuizCompleteRequest,
    database: Session = Depends(get_db),
) -> QuizCompleteResponse:
    """Grade a quiz without saving attempts (public demo)."""

    _require_public_mode()
    try:
        ensure_quiz_published_in_public_class(
            database, class_id=class_id, quiz_id=quiz_id
        )
    except ClassServiceError as error:
        raise _http_error(error) from error

    answer_map = {
        item.question_id: {"answer": item.answer, "code": item.code}
        for item in payload.answers
    }
    result = complete_quiz(
        database,
        user_id=0,
        quiz_id=quiz_id,
        answers=answer_map,
        class_id=class_id,
        persist=False,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quiz not found",
        )
    return QuizCompleteResponse(**result)


@router.post(
    "/questions/{question_id}/check",
    response_model=AnswerCheckResponse,
)
def check_public_mcq(
    question_id: int,
    payload: AnswerCheckRequest,
    database: Session = Depends(get_db),
) -> AnswerCheckResponse:
    _require_public_mode()
    question = get_question(database, question_id)
    if question is None or question.type != "mcq":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="MCQ question not found",
        )
    if question.visibility != "public":
        in_public = False
        for classroom in list_public_classes(database):
            if question_published_in_class(
                database, class_id=classroom.id, question_id=question_id
            ):
                in_public = True
                break
        if not in_public:
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


@router.post("/code/run", response_model=CodeRunResponse)
def run_public_code(payload: CodeRunRequest) -> CodeRunResponse:
    _require_public_mode()
    try:
        result = run_python_code(payload.code)
    except DockerExecutionError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
    return CodeRunResponse(
        stdout=result.stdout,
        stderr=result.stderr,
        exit_code=result.exit_code,
        timed_out=result.timed_out,
        detail="Execution timed out." if result.timed_out else None,
    )


@router.post("/submissions/grade", response_model=SubmissionResponse)
def grade_public_submission(
    payload: SubmissionCreate,
    database: Session = Depends(get_db),
) -> SubmissionResponse:
    """Grade coding/MCQ without saving (public demo)."""

    _require_public_mode()
    question_id = payload.question_id
    if payload.class_id is not None:
        try:
            get_public_classroom(database, payload.class_id)
        except ClassServiceError as error:
            raise _http_error(error) from error
        if not question_published_in_class(
            database, class_id=payload.class_id, question_id=question_id
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Question not found in this class",
            )
    else:
        question = get_question(database, question_id)
        if question is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Question not found",
            )
        if question.visibility != "public":
            in_public = False
            for classroom in list_public_classes(database):
                if question_published_in_class(
                    database, class_id=classroom.id, question_id=question_id
                ):
                    in_public = True
                    break
            if not in_public:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Question not found",
                )

    try:
        graded = grade_without_saving(
            database,
            question_id=question_id,
            answer=payload.answer,
            code=payload.code,
        )
    except SubmissionError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
    return SubmissionResponse.model_validate(graded)
