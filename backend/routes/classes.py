"""Class management, enrollment, and class-scoped student content."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.dependencies import get_current_user, require_admin
from backend.models.user import User
from backend.schemas.classroom import (
    AnnouncementCreate,
    AnnouncementResponse,
    ClassCreate,
    ClassEnrollRequest,
    ClassPerformanceRow,
    ClassPublicCard,
    ClassPublishModules,
    ClassPublishQuizzes,
    ClassResponse,
    ClassUpdate,
)
from backend.schemas.path import PathModuleResponse
from backend.schemas.question import QuestionResponse
from backend.schemas.quiz import QuizCardResponse, QuizCompleteRequest, QuizCompleteResponse
from backend.services.class_service import (
    ClassServiceError,
    build_class_path,
    class_performance,
    classroom_to_dict,
    create_announcement,
    create_classroom,
    delete_announcement,
    delete_classroom,
    enroll_student,
    ensure_quiz_published_in_class,
    get_class_quiz_cards,
    get_classroom_for_access,
    list_announcements,
    list_enrolled_classes,
    list_owned_classes,
    list_public_classes,
    regenerate_enrollment_code,
    set_class_modules,
    set_class_quizzes,
    update_classroom,
)
from backend.services.question_service import question_to_student_dict
from backend.services.quiz_service import complete_quiz, get_quiz_questions

router = APIRouter(prefix="/classes", tags=["Classes"])


def _http_error(error: ClassServiceError) -> HTTPException:
    message = str(error)
    code = status.HTTP_400_BAD_REQUEST
    lowered = message.lower()
    if message in {
        "Class not found",
        "Quiz is not published in this class",
        "Announcement not found",
    }:
        code = status.HTTP_404_NOT_FOUND
    elif (
        "owner" in lowered
        or "not enrolled" in lowered
        or "private quiz" in lowered
        or "cannot publish" in lowered
    ):
        code = status.HTTP_403_FORBIDDEN
    elif message in {
        "Only the class owner can manage this class",
        "Not enrolled in this class",
        "Teachers manage classes; students enroll",
    }:
        code = status.HTTP_403_FORBIDDEN
    return HTTPException(status_code=code, detail=message)


def _to_response(classroom, *, include_code: bool) -> ClassResponse:
    return ClassResponse.model_validate(
        classroom_to_dict(classroom, include_code=include_code)
    )


@router.post("", response_model=ClassResponse, status_code=status.HTTP_201_CREATED)
def create_class_route(
    payload: ClassCreate,
    current_user: User = Depends(require_admin),
    database: Session = Depends(get_db),
) -> ClassResponse:
    try:
        classroom = create_classroom(
            database, owner_id=current_user.id, payload=payload
        )
    except ClassServiceError as error:
        raise _http_error(error) from error
    return _to_response(classroom, include_code=True)


@router.get("/mine", response_model=list[ClassResponse])
def list_my_classes(
    current_user: User = Depends(require_admin),
    database: Session = Depends(get_db),
) -> list[ClassResponse]:
    return [
        _to_response(item, include_code=True)
        for item in list_owned_classes(database, current_user.id)
    ]


@router.get("/public", response_model=list[ClassPublicCard])
def browse_public_classes(
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> list[ClassPublicCard]:
    cards = []
    for classroom in list_public_classes(
        database, exclude_user_id=current_user.id
    ):
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


@router.get("/enrolled", response_model=list[ClassResponse])
def list_student_classes(
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> list[ClassResponse]:
    return [
        _to_response(item, include_code=False)
        for item in list_enrolled_classes(database, current_user.id)
    ]


@router.post("/enroll", response_model=ClassResponse)
def enroll_in_class(
    payload: ClassEnrollRequest,
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> ClassResponse:
    try:
        classroom = enroll_student(
            database,
            user_id=current_user.id,
            code=payload.code,
            class_id=payload.class_id,
        )
    except ClassServiceError as error:
        raise _http_error(error) from error
    return _to_response(classroom, include_code=False)


@router.get("/{class_id}", response_model=ClassResponse)
def get_class_detail(
    class_id: int,
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> ClassResponse:
    try:
        classroom = get_classroom_for_access(
            database, class_id, user_id=current_user.id
        )
    except ClassServiceError as error:
        raise _http_error(error) from error
    include_code = classroom.owner_id == current_user.id
    return _to_response(classroom, include_code=include_code)


@router.patch("/{class_id}", response_model=ClassResponse)
def patch_class(
    class_id: int,
    payload: ClassUpdate,
    current_user: User = Depends(require_admin),
    database: Session = Depends(get_db),
) -> ClassResponse:
    try:
        classroom = update_classroom(
            database,
            class_id,
            owner_id=current_user.id,
            payload=payload,
        )
    except ClassServiceError as error:
        raise _http_error(error) from error
    return _to_response(classroom, include_code=True)


@router.delete("/{class_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_class(
    class_id: int,
    current_user: User = Depends(require_admin),
    database: Session = Depends(get_db),
) -> None:
    try:
        delete_classroom(database, class_id, owner_id=current_user.id)
    except ClassServiceError as error:
        raise _http_error(error) from error


@router.post("/{class_id}/regenerate-code", response_model=ClassResponse)
def regenerate_code(
    class_id: int,
    current_user: User = Depends(require_admin),
    database: Session = Depends(get_db),
) -> ClassResponse:
    try:
        classroom = regenerate_enrollment_code(
            database, class_id, owner_id=current_user.id
        )
    except ClassServiceError as error:
        raise _http_error(error) from error
    return _to_response(classroom, include_code=True)


@router.put("/{class_id}/quizzes", response_model=ClassResponse)
def publish_quizzes(
    class_id: int,
    payload: ClassPublishQuizzes,
    current_user: User = Depends(require_admin),
    database: Session = Depends(get_db),
) -> ClassResponse:
    try:
        classroom = set_class_quizzes(
            database,
            class_id,
            owner_id=current_user.id,
            quiz_ids=payload.quiz_ids,
        )
    except ClassServiceError as error:
        raise _http_error(error) from error
    return _to_response(classroom, include_code=True)


@router.put("/{class_id}/modules", response_model=ClassResponse)
def publish_modules(
    class_id: int,
    payload: ClassPublishModules,
    current_user: User = Depends(require_admin),
    database: Session = Depends(get_db),
) -> ClassResponse:
    try:
        classroom = set_class_modules(
            database,
            class_id,
            owner_id=current_user.id,
            module_ids=payload.module_ids,
        )
    except ClassServiceError as error:
        raise _http_error(error) from error
    return _to_response(classroom, include_code=True)


@router.get("/{class_id}/announcements", response_model=list[AnnouncementResponse])
def read_announcements(
    class_id: int,
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> list[AnnouncementResponse]:
    try:
        rows = list_announcements(database, class_id, user_id=current_user.id)
    except ClassServiceError as error:
        raise _http_error(error) from error
    return [AnnouncementResponse.model_validate(row) for row in rows]


@router.post(
    "/{class_id}/announcements",
    response_model=AnnouncementResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_announcement(
    class_id: int,
    payload: AnnouncementCreate,
    current_user: User = Depends(require_admin),
    database: Session = Depends(get_db),
) -> AnnouncementResponse:
    try:
        row = create_announcement(
            database,
            class_id,
            owner_id=current_user.id,
            title=payload.title,
            body=payload.body,
        )
    except ClassServiceError as error:
        raise _http_error(error) from error
    return AnnouncementResponse.model_validate(row)


@router.delete(
    "/{class_id}/announcements/{announcement_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_announcement(
    class_id: int,
    announcement_id: int,
    current_user: User = Depends(require_admin),
    database: Session = Depends(get_db),
) -> None:
    try:
        delete_announcement(
            database,
            class_id,
            announcement_id,
            owner_id=current_user.id,
        )
    except ClassServiceError as error:
        raise _http_error(error) from error


@router.get("/{class_id}/performance", response_model=list[ClassPerformanceRow])
def read_performance(
    class_id: int,
    current_user: User = Depends(require_admin),
    database: Session = Depends(get_db),
) -> list[ClassPerformanceRow]:
    try:
        rows = class_performance(database, class_id, owner_id=current_user.id)
    except ClassServiceError as error:
        raise _http_error(error) from error
    return [ClassPerformanceRow.model_validate(row) for row in rows]


@router.get("/{class_id}/quizzes", response_model=list[QuizCardResponse])
def read_class_quizzes(
    class_id: int,
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> list[QuizCardResponse]:
    try:
        cards = get_class_quiz_cards(
            database, class_id, user_id=current_user.id
        )
    except ClassServiceError as error:
        raise _http_error(error) from error
    return [QuizCardResponse.model_validate(card) for card in cards]


@router.get(
    "/{class_id}/quizzes/{quiz_id}/questions",
    response_model=list[QuestionResponse],
)
def read_class_quiz_questions(
    class_id: int,
    quiz_id: int,
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> list[dict]:
    try:
        ensure_quiz_published_in_class(
            database,
            class_id=class_id,
            quiz_id=quiz_id,
            user_id=current_user.id,
        )
    except ClassServiceError as error:
        raise _http_error(error) from error
    return [
        question_to_student_dict(item)
        for item in get_quiz_questions(database, quiz_id)
    ]


@router.post(
    "/{class_id}/quizzes/{quiz_id}/complete",
    response_model=QuizCompleteResponse,
)
def complete_class_quiz(
    class_id: int,
    quiz_id: int,
    payload: QuizCompleteRequest,
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> QuizCompleteResponse:
    try:
        ensure_quiz_published_in_class(
            database,
            class_id=class_id,
            quiz_id=quiz_id,
            user_id=current_user.id,
        )
    except ClassServiceError as error:
        raise _http_error(error) from error

    answer_map = {
        item.question_id: {"answer": item.answer, "code": item.code}
        for item in payload.answers
    }
    result = complete_quiz(
        database,
        user_id=current_user.id,
        quiz_id=quiz_id,
        answers=answer_map,
        class_id=class_id,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Quiz not found",
        )
    return QuizCompleteResponse(**result)


@router.get("/{class_id}/path", response_model=list[PathModuleResponse])
def read_class_path(
    class_id: int,
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> list[dict]:
    try:
        return build_class_path(database, class_id, user_id=current_user.id)
    except ClassServiceError as error:
        raise _http_error(error) from error
