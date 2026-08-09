"""Teacher/admin routes for question bank, quizzes, and coding path."""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.dependencies import require_admin
from backend.models.user import User
from backend.schemas.path import (
    ModuleAdminResponse,
    ModuleBlocksUpdate,
    ModuleCreate,
    ModuleLevelsUpdate,
    ModuleUpdate,
)
from backend.schemas.question import (
    QuestionAdminResponse,
    QuestionCreate,
    QuestionUpdate,
    SubjectResponse,
    TopicResponse,
)
from backend.schemas.quiz import (
    QuizAdminResponse,
    QuizCreate,
    QuizMembershipUpdate,
    QuizUpdate,
)
from backend.services.media_service import (
    MediaServiceError,
    latex_snippet_for_media,
    latex_snippet_for_url,
    list_media_library,
    save_upload,
)
from backend.services.path_service import (
    PathServiceError,
    create_module,
    delete_module,
    get_module,
    list_modules,
    module_to_admin_dict,
    set_module_blocks,
    set_module_levels,
    update_module,
)
from backend.services.question_service import (
    QuestionServiceError,
    clone_question,
    create_question,
    delete_question,
    list_questions,
    question_to_admin_dict,
    update_question,
)
from backend.services.quiz_service import (
    QuizServiceError,
    clone_quiz,
    create_quiz,
    delete_quiz,
    get_quiz,
    list_quizzes,
    quiz_to_admin_dict,
    set_quiz_questions,
    update_quiz,
)
from backend.services.topic_service import (
    get_or_create_subject,
    get_or_create_topics,
    list_topics,
    subject_tree,
)

router = APIRouter(prefix="/admin", tags=["Admin"])


def _path_http_error(error: PathServiceError) -> HTTPException:
    message = str(error)
    lowered = message.lower()
    if "owner" in lowered:
        code = status.HTTP_403_FORBIDDEN
    elif "not found" in lowered:
        code = status.HTTP_404_NOT_FOUND
    else:
        code = status.HTTP_400_BAD_REQUEST
    return HTTPException(status_code=code, detail=message)


class TopicCreate(BaseModel):
    """Create an area inside a subject."""

    name: str = Field(min_length=2, max_length=100)
    subject: str = Field(default="python", min_length=1, max_length=100)


class SubjectCreate(BaseModel):
    """Create a top-level subject (python, math, java, …)."""

    name: str = Field(min_length=2, max_length=100)


def _topic_payload(topic) -> TopicResponse:
    return TopicResponse(
        id=topic.id,
        name=topic.name,
        subject_id=topic.subject_id,
        subject=topic.subject.name if topic.subject else None,
    )


def _quiz_admin_payload(quiz, *, actor_id: int | None = None) -> QuizAdminResponse:
    return QuizAdminResponse.model_validate(
        quiz_to_admin_dict(quiz, actor_id=actor_id)
    )


def _module_admin_payload(module) -> ModuleAdminResponse:
    return ModuleAdminResponse.model_validate(module_to_admin_dict(module))


@router.get("/subjects", response_model=list[SubjectResponse])
def admin_list_subjects(
    _: User = Depends(require_admin),
    database: Session = Depends(get_db),
) -> list[dict]:
    """List subjects with nested areas (e.g. python → loops)."""

    return subject_tree(database)


@router.post(
    "/subjects",
    response_model=SubjectResponse,
    status_code=status.HTTP_201_CREATED,
)
def admin_create_subject(
    payload: SubjectCreate,
    _: User = Depends(require_admin),
    database: Session = Depends(get_db),
) -> dict:
    subject = get_or_create_subject(database, payload.name)
    database.commit()
    return {"id": subject.id, "name": subject.name, "areas": []}


@router.get("/topics", response_model=list[TopicResponse])
def admin_list_topics(
    _: User = Depends(require_admin),
    database: Session = Depends(get_db),
    subject: str | None = None,
) -> list[TopicResponse]:
    """List areas, optionally filtered by subject."""

    return [_topic_payload(item) for item in list_topics(database, subject=subject)]


@router.post(
    "/topics",
    response_model=TopicResponse,
    status_code=status.HTTP_201_CREATED,
)
def admin_create_topic(
    payload: TopicCreate,
    _: User = Depends(require_admin),
    database: Session = Depends(get_db),
) -> TopicResponse:
    """Create an area inside a subject."""

    topics = get_or_create_topics(
        database, [payload.name], subject=payload.subject
    )
    database.commit()
    topic = topics[0]
    # Reload subject relationship
    refreshed = list_topics(database, subject=payload.subject)
    match = next((item for item in refreshed if item.id == topic.id), topic)
    return _topic_payload(match)


@router.get("/questions", response_model=list[QuestionAdminResponse])
def admin_list_questions(
    current_user: User = Depends(require_admin),
    database: Session = Depends(get_db),
    subject: str | None = None,
    topic: str | None = None,
    difficulty: str | None = None,
    question_type: str | None = None,
    search: str | None = None,
    visibility: str | None = None,
    mine_only: bool = False,
    limit: int = 1000,
) -> list[dict]:
    """Question bank for teachers: public items + own private items."""

    return [
        question_to_admin_dict(item, actor_id=current_user.id)
        for item in list_questions(
            database,
            subject=subject,
            topic=topic,
            difficulty=difficulty,
            question_type=question_type,
            search=search,
            visibility=visibility,
            viewer_id=current_user.id,
            owner_only=mine_only,
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
    current_user: User = Depends(require_admin),
    database: Session = Depends(get_db),
) -> dict:
    try:
        question = create_question(
            database, payload, owner_id=current_user.id
        )
    except QuestionServiceError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return question_to_admin_dict(question, actor_id=current_user.id)


@router.post(
    "/questions/{question_id}/clone",
    response_model=QuestionAdminResponse,
    status_code=status.HTTP_201_CREATED,
)
def admin_clone_question(
    question_id: int,
    current_user: User = Depends(require_admin),
    database: Session = Depends(get_db),
) -> dict:
    """Copy a shared bank question for quiz-local edits (original unchanged)."""

    try:
        question = clone_question(
            database, question_id, owner_id=current_user.id
        )
    except QuestionServiceError as error:
        message = str(error)
        code = (
            status.HTTP_403_FORBIDDEN
            if "private" in message.lower()
            else status.HTTP_404_NOT_FOUND
        )
        raise HTTPException(status_code=code, detail=message) from error
    return question_to_admin_dict(question, actor_id=current_user.id)


@router.put("/questions/{question_id}", response_model=QuestionAdminResponse)
def admin_update_question(
    question_id: int,
    payload: QuestionUpdate,
    current_user: User = Depends(require_admin),
    database: Session = Depends(get_db),
) -> dict:
    try:
        question = update_question(
            database, question_id, payload, actor_id=current_user.id
        )
    except QuestionServiceError as error:
        message = str(error)
        code = (
            status.HTTP_403_FORBIDDEN
            if "author" in message.lower()
            else status.HTTP_404_NOT_FOUND
        )
        raise HTTPException(status_code=code, detail=message) from error
    except ValidationError as error:
        raise HTTPException(status_code=422, detail=error.errors()) from error
    return question_to_admin_dict(question, actor_id=current_user.id)


@router.delete("/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_question(
    question_id: int,
    current_user: User = Depends(require_admin),
    database: Session = Depends(get_db),
) -> None:
    try:
        delete_question(database, question_id, actor_id=current_user.id)
    except QuestionServiceError as error:
        message = str(error)
        if message == "Question not found":
            code = status.HTTP_404_NOT_FOUND
        elif "author" in message.lower() or "cannot be deleted" in message.lower():
            code = status.HTTP_403_FORBIDDEN
        else:
            code = status.HTTP_409_CONFLICT
        raise HTTPException(status_code=code, detail=message) from error


@router.get("/quizzes", response_model=list[QuizAdminResponse])
def admin_list_quizzes(
    current_user: User = Depends(require_admin),
    database: Session = Depends(get_db),
) -> list[QuizAdminResponse]:
    return [
        _quiz_admin_payload(quiz, actor_id=current_user.id)
        for quiz in list_quizzes(database, actor_id=current_user.id)
    ]


@router.post(
    "/quizzes",
    response_model=QuizAdminResponse,
    status_code=status.HTTP_201_CREATED,
)
def admin_create_quiz(
    payload: QuizCreate,
    current_user: User = Depends(require_admin),
    database: Session = Depends(get_db),
) -> QuizAdminResponse:
    try:
        quiz = create_quiz(database, payload, owner_id=current_user.id)
    except QuizServiceError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return _quiz_admin_payload(quiz, actor_id=current_user.id)


@router.post(
    "/quizzes/{quiz_id}/clone",
    response_model=QuizAdminResponse,
    status_code=status.HTTP_201_CREATED,
)
def admin_clone_quiz(
    quiz_id: int,
    current_user: User = Depends(require_admin),
    database: Session = Depends(get_db),
) -> QuizAdminResponse:
    """Deep-copy a global/private quiz for class use (source unchanged)."""

    try:
        quiz = clone_quiz(database, quiz_id, owner_id=current_user.id)
    except QuizServiceError as error:
        message = str(error)
        code = (
            status.HTTP_403_FORBIDDEN
            if "private" in message.lower()
            else status.HTTP_404_NOT_FOUND
        )
        raise HTTPException(status_code=code, detail=message) from error
    return _quiz_admin_payload(quiz, actor_id=current_user.id)


@router.put("/quizzes/{quiz_id}", response_model=QuizAdminResponse)
def admin_update_quiz(
    quiz_id: int,
    payload: QuizUpdate,
    current_user: User = Depends(require_admin),
    database: Session = Depends(get_db),
) -> QuizAdminResponse:
    try:
        quiz = update_quiz(
            database, quiz_id, payload, actor_id=current_user.id
        )
    except QuizServiceError as error:
        message = str(error)
        code = (
            status.HTTP_403_FORBIDDEN
            if "author" in message.lower()
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=code, detail=message) from error
    return _quiz_admin_payload(quiz, actor_id=current_user.id)


@router.put("/quizzes/{quiz_id}/questions", response_model=QuizAdminResponse)
def admin_set_quiz_questions(
    quiz_id: int,
    payload: QuizMembershipUpdate,
    current_user: User = Depends(require_admin),
    database: Session = Depends(get_db),
) -> QuizAdminResponse:
    quiz = get_quiz(database, quiz_id)
    if quiz is None:
        raise HTTPException(status_code=404, detail="Quiz not found")
    if quiz.owner_id not in (None, current_user.id):
        raise HTTPException(
            status_code=403, detail="Only the author can edit this quiz"
        )
    try:
        quiz = set_quiz_questions(
            database,
            quiz_id,
            payload.question_ids,
            actor_id=current_user.id,
        )
    except QuizServiceError as error:
        message = str(error)
        code = (
            status.HTTP_403_FORBIDDEN
            if "private" in message.lower()
            else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=code, detail=message) from error
    return _quiz_admin_payload(quiz, actor_id=current_user.id)


@router.delete("/quizzes/{quiz_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_quiz(
    quiz_id: int,
    current_user: User = Depends(require_admin),
    database: Session = Depends(get_db),
) -> None:
    try:
        delete_quiz(database, quiz_id, actor_id=current_user.id)
    except QuizServiceError as error:
        message = str(error)
        code = (
            status.HTTP_403_FORBIDDEN
            if "author" in message.lower()
            else status.HTTP_404_NOT_FOUND
        )
        raise HTTPException(status_code=code, detail=message) from error


@router.get("/modules", response_model=list[ModuleAdminResponse])
def admin_list_modules(
    class_id: int | None = None,
    current_user: User = Depends(require_admin),
    database: Session = Depends(get_db),
) -> list[ModuleAdminResponse]:
    try:
        modules = list_modules(
            database, class_id=class_id, owner_id=current_user.id
        )
    except PathServiceError as error:
        raise _path_http_error(error) from error
    return [_module_admin_payload(module) for module in modules]


@router.post(
    "/modules",
    response_model=ModuleAdminResponse,
    status_code=status.HTTP_201_CREATED,
)
def admin_create_module(
    payload: ModuleCreate,
    current_user: User = Depends(require_admin),
    database: Session = Depends(get_db),
) -> ModuleAdminResponse:
    try:
        module = create_module(
            database, payload, actor_id=current_user.id
        )
    except PathServiceError as error:
        raise _path_http_error(error) from error
    return _module_admin_payload(module)


@router.put("/modules/{module_id}", response_model=ModuleAdminResponse)
def admin_update_module(
    module_id: int,
    payload: ModuleUpdate,
    current_user: User = Depends(require_admin),
    database: Session = Depends(get_db),
) -> ModuleAdminResponse:
    try:
        module = update_module(
            database, module_id, payload, actor_id=current_user.id
        )
    except PathServiceError as error:
        raise _path_http_error(error) from error
    return _module_admin_payload(module)


@router.put("/modules/{module_id}/levels", response_model=ModuleAdminResponse)
def admin_set_module_levels(
    module_id: int,
    payload: ModuleLevelsUpdate,
    current_user: User = Depends(require_admin),
    database: Session = Depends(get_db),
) -> ModuleAdminResponse:
    """Legacy: set coding blocks from question ids."""

    try:
        module = set_module_levels(
            database,
            module_id,
            payload.question_ids,
            actor_id=current_user.id,
        )
    except PathServiceError as error:
        raise _path_http_error(error) from error
    return _module_admin_payload(module)


@router.put("/modules/{module_id}/blocks", response_model=ModuleAdminResponse)
def admin_set_module_blocks(
    module_id: int,
    payload: ModuleBlocksUpdate,
    current_user: User = Depends(require_admin),
    database: Session = Depends(get_db),
) -> ModuleAdminResponse:
    try:
        module = set_module_blocks(
            database,
            module_id,
            payload.blocks,
            actor_id=current_user.id,
        )
    except PathServiceError as error:
        raise _path_http_error(error) from error
    return _module_admin_payload(module)


@router.delete("/modules/{module_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_module(
    module_id: int,
    current_user: User = Depends(require_admin),
    database: Session = Depends(get_db),
) -> None:
    try:
        delete_module(database, module_id, actor_id=current_user.id)
    except PathServiceError as error:
        raise _path_http_error(error) from error


@router.get("/modules/{module_id}", response_model=ModuleAdminResponse)
def admin_get_module(
    module_id: int,
    current_user: User = Depends(require_admin),
    database: Session = Depends(get_db),
) -> ModuleAdminResponse:
    try:
        module = get_module(database, module_id, actor_id=current_user.id)
    except PathServiceError as error:
        raise _path_http_error(error) from error
    if module is None:
        raise HTTPException(status_code=404, detail="Module not found")
    return _module_admin_payload(module)


class MediaLinkRequest(BaseModel):
    """Register an external/internal URL as a LaTeX snippet."""

    url: str = Field(min_length=3, max_length=2000)
    label: str | None = Field(default=None, max_length=200)


@router.get("/media")
def admin_list_media(
    _: User = Depends(require_admin),
) -> list[dict]:
    """List uploaded media files for reuse in modules."""

    return list_media_library()


@router.post("/media/upload")
async def admin_upload_media(
    file: UploadFile = File(...),
    current_user: User = Depends(require_admin),
) -> dict:
    """Upload a file into the local media/ folder (teacher only)."""

    raw = await file.read()
    try:
        saved = save_upload(
            filename=file.filename or "upload.bin",
            content=raw,
            content_type=file.content_type,
        )
    except MediaServiceError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    snippet = latex_snippet_for_media(
        url=saved["url"],
        kind=saved["kind"],
        label=saved["filename"],
    )
    return {**saved, "latex": snippet}


@router.post("/media/link")
def admin_media_link(
    payload: MediaLinkRequest,
    current_user: User = Depends(require_admin),
) -> dict:
    """Turn a URL into a LaTeX href / YouTube / media snippet."""

    url = payload.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")
    snippet = latex_snippet_for_url(url, label=payload.label)
    kind = "image" if "includegraphics" in snippet else "link"
    return {"url": url, "kind": kind, "latex": snippet}
