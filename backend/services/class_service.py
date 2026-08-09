"""Class CRUD, enrollment, publishing, and class-scoped performance."""

from __future__ import annotations

import secrets
import string
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.models.classroom import (
    ClassAnnouncement,
    ClassEnrollment,
    ClassModule,
    ClassQuiz,
    Classroom,
)
from backend.models.coding_module import CodingModule, ModuleBlock
from backend.models.question import Question
from backend.models.quiz import Quiz
from backend.models.quiz_attempt import QuizAttempt
from backend.models.quiz_question import QuizQuestion
from backend.models.submission import Submission
from backend.models.user import User
from backend.schemas.classroom import ClassCreate, ClassUpdate
from backend.services.path_service import get_module
from backend.services.quiz_service import get_quiz, get_student_quiz_stats, quiz_topics


class ClassServiceError(ValueError):
    """Raised for class operations that cannot complete."""


_CODE_ALPHABET = string.ascii_uppercase + string.digits


def _generate_enrollment_code(database: Session) -> str:
    """Return a unique short enrollment code."""

    for _ in range(20):
        code = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(8))
        exists = database.scalars(
            select(Classroom.id).where(Classroom.enrollment_code == code)
        ).first()
        if exists is None:
            return code
    raise ClassServiceError("Could not generate a unique enrollment code")


def _load_classroom(database: Session, class_id: int) -> Classroom | None:
    statement = (
        select(Classroom)
        .options(
            selectinload(Classroom.enrollments),
            selectinload(Classroom.class_quizzes).selectinload(ClassQuiz.quiz)
            .selectinload(Quiz.quiz_questions)
            .selectinload(QuizQuestion.question)
            .selectinload(Question.topic_tags),
            selectinload(Classroom.class_modules)
            .selectinload(ClassModule.module)
            .selectinload(CodingModule.blocks)
            .selectinload(ModuleBlock.question)
            .selectinload(Question.topic_tags),
            selectinload(Classroom.modules)
            .selectinload(CodingModule.blocks)
            .selectinload(ModuleBlock.question)
            .selectinload(Question.topic_tags),
            selectinload(Classroom.owner),
        )
        .where(Classroom.id == class_id)
    )
    return database.scalars(statement).unique().first()


def classroom_to_dict(
    classroom: Classroom,
    *,
    include_code: bool = False,
) -> dict:
    """Serialize a classroom for API responses."""

    published_quizzes = [
        link for link in classroom.class_quizzes if link.is_published
    ]
    owned_modules = sorted(
        classroom.modules,
        key=lambda item: (item.position, item.id),
    )
    return {
        "id": classroom.id,
        "title": classroom.title,
        "description": classroom.description or "",
        "owner_id": classroom.owner_id,
        "visibility": classroom.visibility,
        "enrollment_code": classroom.enrollment_code if include_code else None,
        "is_active": classroom.is_active,
        "created_at": classroom.created_at,
        "quiz_count": len(published_quizzes),
        "module_count": len(owned_modules),
        "student_count": len(classroom.enrollments),
        "quiz_ids": [link.quiz_id for link in published_quizzes],
        "module_ids": [module.id for module in owned_modules],
    }


def require_owner(classroom: Classroom, user_id: int) -> None:
    if classroom.owner_id != user_id:
        raise ClassServiceError("Only the class owner can manage this class")


def is_enrolled(database: Session, *, class_id: int, user_id: int) -> bool:
    row = database.scalars(
        select(ClassEnrollment.id).where(
            ClassEnrollment.class_id == class_id,
            ClassEnrollment.user_id == user_id,
        )
    ).first()
    return row is not None


def create_classroom(
    database: Session,
    *,
    owner_id: int,
    payload: ClassCreate,
) -> Classroom:
    classroom = Classroom(
        title=payload.title.strip(),
        description=(payload.description or "").strip(),
        owner_id=owner_id,
        visibility=payload.visibility.value,
        enrollment_code=_generate_enrollment_code(database),
        is_active=True,
    )
    database.add(classroom)
    database.commit()
    refreshed = _load_classroom(database, classroom.id)
    if refreshed is None:
        raise ClassServiceError("Class not found after create")
    return refreshed


def list_owned_classes(database: Session, owner_id: int) -> list[Classroom]:
    statement = (
        select(Classroom)
        .options(
            selectinload(Classroom.enrollments),
            selectinload(Classroom.class_quizzes),
            selectinload(Classroom.class_modules),
            selectinload(Classroom.modules),
            selectinload(Classroom.owner),
        )
        .where(Classroom.owner_id == owner_id)
        .order_by(Classroom.id.desc())
    )
    return list(database.scalars(statement).unique().all())


def list_public_classes(
    database: Session,
    *,
    exclude_user_id: int | None = None,
) -> list[Classroom]:
    statement = (
        select(Classroom)
        .options(
            selectinload(Classroom.enrollments),
            selectinload(Classroom.class_quizzes),
            selectinload(Classroom.class_modules),
            selectinload(Classroom.modules),
            selectinload(Classroom.owner),
        )
        .where(
            Classroom.visibility == "public",
            Classroom.is_active.is_(True),
        )
        .order_by(Classroom.title)
    )
    classes = list(database.scalars(statement).unique().all())
    if exclude_user_id is None:
        return classes
    return [
        item
        for item in classes
        if not any(e.user_id == exclude_user_id for e in item.enrollments)
    ]


def list_enrolled_classes(database: Session, user_id: int) -> list[Classroom]:
    statement = (
        select(Classroom)
        .join(ClassEnrollment, ClassEnrollment.class_id == Classroom.id)
        .options(
            selectinload(Classroom.enrollments),
            selectinload(Classroom.class_quizzes),
            selectinload(Classroom.class_modules),
            selectinload(Classroom.modules),
            selectinload(Classroom.owner),
        )
        .where(
            ClassEnrollment.user_id == user_id,
            Classroom.is_active.is_(True),
        )
        .order_by(Classroom.title)
    )
    return list(database.scalars(statement).unique().all())


def get_public_classroom(database: Session, class_id: int) -> Classroom:
    """Return an active public class or raise ClassServiceError."""

    classroom = _load_classroom(database, class_id)
    if (
        classroom is None
        or not classroom.is_active
        or classroom.visibility != "public"
    ):
        raise ClassServiceError("Class not found")
    return classroom


def resolve_public_demo_class(database: Session) -> Classroom | None:
    """Preferred public class from settings, else first active public class."""

    from backend.config import settings

    if settings.public_class_id is not None:
        try:
            return get_public_classroom(database, settings.public_class_id)
        except ClassServiceError:
            return None
    classes = list_public_classes(database)
    return classes[0] if classes else None


def build_public_class_path(database: Session, class_id: int) -> list[dict]:
    """Lecture path for a public class (no progress markers)."""

    classroom = get_public_classroom(database, class_id)
    from backend.services.path_service import serialize_module_for_student

    payload: list[dict] = []
    for module in sorted(
        classroom.modules, key=lambda item: (item.position, item.id)
    ):
        payload.append(
            serialize_module_for_student(module, done_question_ids=set())
        )
    return payload


def get_public_class_quiz_cards(database: Session, class_id: int) -> list[dict]:
    """Published quiz cards for a public class (no attempt history)."""

    classroom = get_public_classroom(database, class_id)
    cards: list[dict] = []
    for link in classroom.class_quizzes:
        if not link.is_published or link.quiz is None:
            continue
        quiz = link.quiz
        cards.append(
            {
                "id": quiz.id,
                "title": quiz.title,
                "description": quiz.description,
                "topics": quiz_topics(quiz),
                "is_timed": quiz.is_timed,
                "duration_seconds": quiz.duration_seconds,
                "question_count": len(quiz.questions),
                "difficulties": sorted({q.difficulty for q in quiz.questions}),
                "question_types": sorted({q.type for q in quiz.questions}),
                "is_completed": False,
                "attempt_count": 0,
                "best_score": None,
                "last_score": None,
            }
        )
    return cards


def ensure_quiz_published_in_public_class(
    database: Session,
    *,
    class_id: int,
    quiz_id: int,
) -> Classroom:
    classroom = get_public_classroom(database, class_id)
    published = {
        link.quiz_id for link in classroom.class_quizzes if link.is_published
    }
    if quiz_id not in published:
        raise ClassServiceError("Quiz is not published in this class")
    return classroom


def list_public_announcements(database: Session, class_id: int) -> list[dict]:
    classroom = get_public_classroom(database, class_id)
    rows = database.scalars(
        select(ClassAnnouncement)
        .options(selectinload(ClassAnnouncement.author))
        .where(ClassAnnouncement.class_id == classroom.id)
        .order_by(ClassAnnouncement.created_at.desc())
    ).all()
    return [
        {
            "id": row.id,
            "class_id": row.class_id,
            "author_id": row.author_id,
            "author_username": row.author.username if row.author else "",
            "title": row.title,
            "body": row.body,
            "created_at": row.created_at,
        }
        for row in rows
    ]


def get_classroom_for_access(
    database: Session,
    class_id: int,
    *,
    user_id: int,
    as_owner: bool = False,
) -> Classroom:
    """Load a class for a student or owner.

    Owners may manage inactive classes (so they can reactivate them).
    Students and non-owners only see active classes.
    """

    classroom = _load_classroom(database, class_id)
    if classroom is None:
        raise ClassServiceError("Class not found")
    if as_owner:
        require_owner(classroom, user_id)
        return classroom
    if not classroom.is_active:
        raise ClassServiceError("Class not found")
    if classroom.owner_id == user_id or is_enrolled(
        database, class_id=class_id, user_id=user_id
    ):
        return classroom
    raise ClassServiceError("Not enrolled in this class")


def update_classroom(
    database: Session,
    class_id: int,
    *,
    owner_id: int,
    payload: ClassUpdate,
) -> Classroom:
    classroom = get_classroom_for_access(
        database, class_id, user_id=owner_id, as_owner=True
    )
    data = payload.model_dump(exclude_unset=True)
    if "visibility" in data and data["visibility"] is not None:
        data["visibility"] = data["visibility"].value
    if "title" in data and data["title"] is not None:
        data["title"] = data["title"].strip()
    if "description" in data and data["description"] is not None:
        data["description"] = data["description"].strip()
    for field, value in data.items():
        setattr(classroom, field, value)
    database.commit()
    refreshed = _load_classroom(database, class_id)
    if refreshed is None:
        raise ClassServiceError("Class not found")
    return refreshed


def regenerate_enrollment_code(
    database: Session,
    class_id: int,
    *,
    owner_id: int,
) -> Classroom:
    classroom = get_classroom_for_access(
        database, class_id, user_id=owner_id, as_owner=True
    )
    classroom.enrollment_code = _generate_enrollment_code(database)
    database.commit()
    refreshed = _load_classroom(database, class_id)
    if refreshed is None:
        raise ClassServiceError("Class not found")
    return refreshed


def delete_classroom(
    database: Session,
    class_id: int,
    *,
    owner_id: int,
) -> None:
    """Permanently delete a class owned by the teacher.

    Cascades enrollments, lecture modules, announcements, and class quiz
    links. Shared/global quizzes are not deleted.
    """

    classroom = get_classroom_for_access(
        database, class_id, user_id=owner_id, as_owner=True
    )
    database.delete(classroom)
    database.commit()


def enroll_student(
    database: Session,
    *,
    user_id: int,
    code: str | None = None,
    class_id: int | None = None,
) -> Classroom:
    user = database.get(User, user_id)
    if user is None:
        raise ClassServiceError("User not found")
    if user.role == "admin":
        raise ClassServiceError("Teachers manage classes; students enroll")

    classroom: Classroom | None = None
    if code:
        classroom = database.scalars(
            select(Classroom).where(
                Classroom.enrollment_code == code.strip().upper(),
                Classroom.is_active.is_(True),
            )
        ).first()
        if classroom is None:
            raise ClassServiceError("Invalid enrollment code")
    else:
        assert class_id is not None
        classroom = _load_classroom(database, class_id)
        if classroom is None or not classroom.is_active:
            raise ClassServiceError("Class not found")
        if classroom.visibility != "public":
            raise ClassServiceError(
                "This class is private — join with an enrollment code"
            )

    if is_enrolled(database, class_id=classroom.id, user_id=user_id):
        raise ClassServiceError("Already enrolled in this class")

    database.add(ClassEnrollment(class_id=classroom.id, user_id=user_id))
    database.commit()
    refreshed = _load_classroom(database, classroom.id)
    if refreshed is None:
        raise ClassServiceError("Class not found")
    return refreshed


def set_class_quizzes(
    database: Session,
    class_id: int,
    *,
    owner_id: int,
    quiz_ids: list[int],
) -> Classroom:
    from backend.services.quiz_service import actor_can_use_quiz

    classroom = get_classroom_for_access(
        database, class_id, user_id=owner_id, as_owner=True
    )
    if len(quiz_ids) != len(set(quiz_ids)):
        raise ClassServiceError("Duplicate quiz ids are not allowed")
    for quiz_id in quiz_ids:
        quiz = get_quiz(database, quiz_id)
        if quiz is None:
            raise ClassServiceError(f"Quiz {quiz_id} not found")
        if not actor_can_use_quiz(quiz, owner_id):
            raise ClassServiceError(
                f"Cannot publish private quiz {quiz_id} you do not own — "
                "import a copy first"
            )

    for link in list(classroom.class_quizzes):
        database.delete(link)
    database.flush()
    for position, quiz_id in enumerate(quiz_ids):
        database.add(
            ClassQuiz(
                class_id=classroom.id,
                quiz_id=quiz_id,
                position=position,
                is_published=True,
            )
        )
    database.commit()
    refreshed = _load_classroom(database, class_id)
    if refreshed is None:
        raise ClassServiceError("Class not found")
    return refreshed


def set_class_modules(
    database: Session,
    class_id: int,
    *,
    owner_id: int,
    module_ids: list[int],
) -> Classroom:
    """Reorder modules that already belong to this class (1st id = first)."""

    classroom = get_classroom_for_access(
        database, class_id, user_id=owner_id, as_owner=True
    )
    if len(module_ids) != len(set(module_ids)):
        raise ClassServiceError("Duplicate module ids are not allowed")

    owned = {module.id: module for module in classroom.modules}
    if set(module_ids) - set(owned):
        raise ClassServiceError("Modules must belong to this class")
    if set(module_ids) != set(owned):
        raise ClassServiceError("Module list must include every class module")

    for link in list(classroom.class_modules):
        database.delete(link)
    database.flush()
    for position, module_id in enumerate(module_ids):
        owned[module_id].position = position
        database.add(
            ClassModule(
                class_id=classroom.id,
                module_id=module_id,
                position=position,
                is_published=True,
            )
        )
    database.commit()
    refreshed = _load_classroom(database, class_id)
    if refreshed is None:
        raise ClassServiceError("Class not found")
    return refreshed


def list_roster(database: Session, class_id: int, *, owner_id: int) -> list[dict]:
    classroom = get_classroom_for_access(
        database, class_id, user_id=owner_id, as_owner=True
    )
    user_ids = [e.user_id for e in classroom.enrollments]
    if not user_ids:
        return []
    users = {
        user.id: user
        for user in database.scalars(select(User).where(User.id.in_(user_ids))).all()
    }
    rows = []
    for enrollment in sorted(
        classroom.enrollments, key=lambda item: item.enrolled_at
    ):
        user = users.get(enrollment.user_id)
        if user is None:
            continue
        rows.append(
            {
                "user_id": user.id,
                "username": user.username,
                "email": user.email,
                "enrolled_at": enrollment.enrolled_at,
            }
        )
    return rows


def get_class_quiz_cards(
    database: Session,
    class_id: int,
    *,
    user_id: int,
) -> list[dict]:
    classroom = get_classroom_for_access(database, class_id, user_id=user_id)
    stats = get_student_quiz_stats(
        database, user_id, class_id=class_id
    )
    cards: list[dict] = []
    for link in classroom.class_quizzes:
        if not link.is_published or link.quiz is None:
            continue
        quiz = link.quiz
        student_stats = stats.get(quiz.id, {})
        cards.append(
            {
                "id": quiz.id,
                "title": quiz.title,
                "description": quiz.description,
                "topics": quiz_topics(quiz),
                "is_timed": quiz.is_timed,
                "duration_seconds": quiz.duration_seconds,
                "question_count": len(quiz.questions),
                "difficulties": sorted({q.difficulty for q in quiz.questions}),
                "question_types": sorted({q.type for q in quiz.questions}),
                "is_completed": bool(student_stats.get("is_completed", False)),
                "attempt_count": int(student_stats.get("attempt_count", 0)),
                "best_score": student_stats.get("best_score"),
                "last_score": student_stats.get("last_score"),
            }
        )
    return cards


def ensure_quiz_published_in_class(
    database: Session,
    *,
    class_id: int,
    quiz_id: int,
    user_id: int,
) -> Classroom:
    classroom = get_classroom_for_access(database, class_id, user_id=user_id)
    published = {
        link.quiz_id for link in classroom.class_quizzes if link.is_published
    }
    if quiz_id not in published:
        raise ClassServiceError("Quiz is not published in this class")
    return classroom


def build_class_path(
    database: Session,
    class_id: int,
    *,
    user_id: int,
) -> list[dict]:
    classroom = get_classroom_for_access(database, class_id, user_id=user_id)
    done_rows = database.scalars(
        select(Submission.question_id).where(
            Submission.user_id == user_id,
            Submission.status == "passed",
            Submission.class_id == class_id,
        )
    ).all()
    done = set(done_rows)
    from backend.services.path_service import serialize_module_for_student

    payload: list[dict] = []
    for module in sorted(
        classroom.modules, key=lambda item: (item.position, item.id)
    ):
        payload.append(
            serialize_module_for_student(module, done_question_ids=done)
        )
    return payload


def question_published_in_class(
    database: Session,
    *,
    class_id: int,
    question_id: int,
) -> bool:
    classroom = _load_classroom(database, class_id)
    if classroom is None:
        return False
    for module in classroom.modules:
        for block in module.blocks:
            if block.question_id == question_id:
                return True
    for link in classroom.class_quizzes:
        if not link.is_published or link.quiz is None:
            continue
        for question in link.quiz.questions:
            if question.id == question_id:
                return True
    return False


def user_can_access_published_question(
    database: Session,
    *,
    user_id: int,
    question_id: int,
) -> bool:
    """True if the user is enrolled in (or owns) a class that exposes the question."""

    class_ids = list(
        database.scalars(
            select(ClassEnrollment.class_id).where(
                ClassEnrollment.user_id == user_id
            )
        ).all()
    )
    owned_ids = list(
        database.scalars(
            select(Classroom.id).where(Classroom.owner_id == user_id)
        ).all()
    )
    for class_id in set(class_ids + owned_ids):
        if question_published_in_class(
            database, class_id=class_id, question_id=question_id
        ):
            return True
    return False


def list_announcements(
    database: Session,
    class_id: int,
    *,
    user_id: int,
) -> list[dict]:
    classroom = get_classroom_for_access(database, class_id, user_id=user_id)
    rows = database.scalars(
        select(ClassAnnouncement)
        .options(selectinload(ClassAnnouncement.author))
        .where(ClassAnnouncement.class_id == classroom.id)
        .order_by(ClassAnnouncement.created_at.desc())
    ).all()
    return [
        {
            "id": row.id,
            "class_id": row.class_id,
            "author_id": row.author_id,
            "author_username": row.author.username if row.author else "",
            "title": row.title,
            "body": row.body,
            "created_at": row.created_at,
        }
        for row in rows
    ]


def create_announcement(
    database: Session,
    class_id: int,
    *,
    owner_id: int,
    title: str,
    body: str,
) -> dict:
    classroom = get_classroom_for_access(
        database, class_id, user_id=owner_id, as_owner=True
    )
    row = ClassAnnouncement(
        class_id=classroom.id,
        author_id=owner_id,
        title=title.strip(),
        body=body.strip(),
    )
    database.add(row)
    database.commit()
    database.refresh(row)
    author = database.get(User, owner_id)
    return {
        "id": row.id,
        "class_id": row.class_id,
        "author_id": row.author_id,
        "author_username": author.username if author else "",
        "title": row.title,
        "body": row.body,
        "created_at": row.created_at,
    }


def delete_announcement(
    database: Session,
    class_id: int,
    announcement_id: int,
    *,
    owner_id: int,
) -> None:
    get_classroom_for_access(database, class_id, user_id=owner_id, as_owner=True)
    row = database.get(ClassAnnouncement, announcement_id)
    if row is None or row.class_id != class_id:
        raise ClassServiceError("Announcement not found")
    database.delete(row)
    database.commit()


def class_performance(
    database: Session,
    class_id: int,
    *,
    owner_id: int,
) -> list[dict]:
    classroom = get_classroom_for_access(
        database, class_id, user_id=owner_id, as_owner=True
    )
    published_quiz_ids = [
        link.quiz_id for link in classroom.class_quizzes if link.is_published
    ]
    coding_question_ids: list[int] = []
    for module in classroom.modules:
        for block in module.blocks:
            if (
                block.type == "coding"
                and block.question
                and block.question.type == "coding"
            ):
                coding_question_ids.append(block.question_id)

    roster = list_roster(database, class_id, owner_id=owner_id)
    rows: list[dict] = []
    for student in roster:
        user_id = student["user_id"]
        stats = get_student_quiz_stats(database, user_id, class_id=class_id)
        completed = 0
        best_scores: list[Decimal] = []
        for quiz_id in published_quiz_ids:
            entry = stats.get(quiz_id)
            if entry and entry.get("is_completed"):
                completed += 1
                if entry.get("best_score") is not None:
                    best_scores.append(Decimal(str(entry["best_score"])))

        passed = 0
        if coding_question_ids:
            passed_ids = set(
                database.scalars(
                    select(Submission.question_id).where(
                        Submission.user_id == user_id,
                        Submission.class_id == class_id,
                        Submission.status == "passed",
                        Submission.question_id.in_(coding_question_ids),
                    )
                ).all()
            )
            passed = len(passed_ids)

        average = (
            (sum(best_scores) / Decimal(len(best_scores))).quantize(
                Decimal("0.01")
            )
            if best_scores
            else None
        )
        rows.append(
            {
                "user_id": user_id,
                "username": student["username"],
                "quizzes_completed": completed,
                "quizzes_published": len(published_quiz_ids),
                "average_best_score": average,
                "coding_levels_passed": passed,
                "coding_levels_total": len(coding_question_ids),
            }
        )
    return rows
