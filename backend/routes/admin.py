"""Teacher/admin routes for question bank, quizzes, and coding path."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.dependencies import require_admin
from backend.models.user import User
from backend.schemas.path import (
    ModuleAdminResponse,
    ModuleCreate,
    ModuleLevelsUpdate,
    ModuleUpdate,
)
from backend.schemas.question import (
    QuestionAdminResponse,
    QuestionCreate,
    QuestionUpdate,
    TopicResponse,
)
from backend.schemas.quiz import (
    QuizAdminResponse,
    QuizCreate,
    QuizMembershipUpdate,
    QuizUpdate,
)
from backend.services.path_service import (
    PathServiceError,
    create_module,
    delete_module,
    get_module,
    list_modules,
    set_module_levels,
    update_module,
)
from backend.services.question_service import (
    QuestionServiceError,
    create_question,
    delete_question,
    list_questions,
    question_to_admin_dict,
    update_question,
)
from backend.services.quiz_service import (
    QuizServiceError,
    create_quiz,
    delete_quiz,
    get_quiz,
    list_quizzes,
    quiz_topics,
    set_quiz_questions,
    update_quiz,
)
from backend.services.topic_service import get_or_create_topics, list_topics

router = APIRouter(prefix="/admin", tags=["Admin"])


class TopicCreate(BaseModel):
    """Create a canonical topic label for the bank."""

    name: str = Field(min_length=2, max_length=100)


def _quiz_admin_payload(quiz) -> QuizAdminResponse:
    return QuizAdminResponse(
        id=quiz.id,
        title=quiz.title,
        description=quiz.description,
        is_timed=quiz.is_timed,
        duration_seconds=quiz.duration_seconds,
        question_ids=[link.question_id for link in quiz.quiz_questions],
        topics=quiz_topics(quiz),
    )


def _module_admin_payload(module) -> ModuleAdminResponse:
    return ModuleAdminResponse(
        id=module.id,
        title=module.title,
        description=module.description,
        position=module.position,
        difficulty_label=module.difficulty_label,
        question_ids=[level.question_id for level in module.levels],
    )


@router.get("/topics", response_model=list[TopicResponse])
def admin_list_topics(
    _: User = Depends(require_admin),
    database: Session = Depends(get_db),
) -> list:
    """List all topic areas for teacher pickers."""

    return list_topics(database)


@router.post(
    "/topics",
    response_model=TopicResponse,
    status_code=status.HTTP_201_CREATED,
)
def admin_create_topic(
    payload: TopicCreate,
    _: User = Depends(require_admin),
    database: Session = Depends(get_db),
) -> object:
    """Create a topic area teachers can attach to questions."""

    topics = get_or_create_topics(database, [payload.name])
    database.commit()
    return topics[0]


@router.get("/questions", response_model=list[QuestionAdminResponse])
def admin_list_questions(
    _: User = Depends(require_admin),
    database: Session = Depends(get_db),
    topic: str | None = None,
    difficulty: str | None = None,
    question_type: str | None = None,
    search: str | None = None,
    limit: int = 1000,
) -> list[dict]:
    """Full question bank for teachers (filterable for large banks)."""

    return [
        question_to_admin_dict(item)
        for item in list_questions(
            database,
            topic=topic,
            difficulty=difficulty,
            question_type=question_type,
            search=search,
            limit=min(max(limit, 1), 5000),
        )
    ]


@router.post(
    "/questions",
    response_model=QuestionAdminResponse,
    status_code=status.HTTP_201_CREATED,
)
def admin_create_question(
    payload: QuestionCreate,
    _: User = Depends(require_admin),
    database: Session = Depends(get_db),
) -> dict:
    try:
        question = create_question(database, payload)
    except QuestionServiceError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return question_to_admin_dict(question)


@router.put("/questions/{question_id}", response_model=QuestionAdminResponse)
def admin_update_question(
    question_id: int,
    payload: QuestionUpdate,
    _: User = Depends(require_admin),
    database: Session = Depends(get_db),
) -> dict:
    try:
        question = update_question(database, question_id, payload)
    except QuestionServiceError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValidationError as error:
        raise HTTPException(status_code=422, detail=error.errors()) from error
    return question_to_admin_dict(question)


@router.delete("/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_question(
    question_id: int,
    _: User = Depends(require_admin),
    database: Session = Depends(get_db),
) -> None:
    try:
        delete_question(database, question_id)
    except QuestionServiceError as error:
        code = 404 if str(error) == "Question not found" else 409
        raise HTTPException(status_code=code, detail=str(error)) from error


@router.get("/quizzes", response_model=list[QuizAdminResponse])
def admin_list_quizzes(
    _: User = Depends(require_admin),
    database: Session = Depends(get_db),
) -> list[QuizAdminResponse]:
    return [_quiz_admin_payload(quiz) for quiz in list_quizzes(database)]


@router.post(
    "/quizzes",
    response_model=QuizAdminResponse,
    status_code=status.HTTP_201_CREATED,
)
def admin_create_quiz(
    payload: QuizCreate,
    _: User = Depends(require_admin),
    database: Session = Depends(get_db),
) -> QuizAdminResponse:
    try:
        quiz = create_quiz(database, payload)
    except QuizServiceError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return _quiz_admin_payload(quiz)


@router.put("/quizzes/{quiz_id}", response_model=QuizAdminResponse)
def admin_update_quiz(
    quiz_id: int,
    payload: QuizUpdate,
    _: User = Depends(require_admin),
    database: Session = Depends(get_db),
) -> QuizAdminResponse:
    try:
        quiz = update_quiz(database, quiz_id, payload)
    except QuizServiceError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return _quiz_admin_payload(quiz)


@router.put("/quizzes/{quiz_id}/questions", response_model=QuizAdminResponse)
def admin_set_quiz_questions(
    quiz_id: int,
    payload: QuizMembershipUpdate,
    _: User = Depends(require_admin),
    database: Session = Depends(get_db),
) -> QuizAdminResponse:
    try:
        quiz = set_quiz_questions(database, quiz_id, payload.question_ids)
    except QuizServiceError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return _quiz_admin_payload(quiz)


@router.delete("/quizzes/{quiz_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_quiz(
    quiz_id: int,
    _: User = Depends(require_admin),
    database: Session = Depends(get_db),
) -> None:
    try:
        delete_quiz(database, quiz_id)
    except QuizServiceError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/modules", response_model=list[ModuleAdminResponse])
def admin_list_modules(
    _: User = Depends(require_admin),
    database: Session = Depends(get_db),
) -> list[ModuleAdminResponse]:
    return [_module_admin_payload(module) for module in list_modules(database)]


@router.post(
    "/modules",
    response_model=ModuleAdminResponse,
    status_code=status.HTTP_201_CREATED,
)
def admin_create_module(
    payload: ModuleCreate,
    _: User = Depends(require_admin),
    database: Session = Depends(get_db),
) -> ModuleAdminResponse:
    try:
        module = create_module(database, payload)
    except PathServiceError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return _module_admin_payload(module)


@router.put("/modules/{module_id}", response_model=ModuleAdminResponse)
def admin_update_module(
    module_id: int,
    payload: ModuleUpdate,
    _: User = Depends(require_admin),
    database: Session = Depends(get_db),
) -> ModuleAdminResponse:
    try:
        module = update_module(database, module_id, payload)
    except PathServiceError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return _module_admin_payload(module)


@router.put("/modules/{module_id}/levels", response_model=ModuleAdminResponse)
def admin_set_module_levels(
    module_id: int,
    payload: ModuleLevelsUpdate,
    _: User = Depends(require_admin),
    database: Session = Depends(get_db),
) -> ModuleAdminResponse:
    try:
        module = set_module_levels(database, module_id, payload.question_ids)
    except PathServiceError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return _module_admin_payload(module)


@router.delete("/modules/{module_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_module(
    module_id: int,
    _: User = Depends(require_admin),
    database: Session = Depends(get_db),
) -> None:
    try:
        delete_module(database, module_id)
    except PathServiceError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.get("/modules/{module_id}", response_model=ModuleAdminResponse)
def admin_get_module(
    module_id: int,
    _: User = Depends(require_admin),
    database: Session = Depends(get_db),
) -> ModuleAdminResponse:
    module = get_module(database, module_id)
    if module is None:
        raise HTTPException(status_code=404, detail="Module not found")
    return _module_admin_payload(module)
