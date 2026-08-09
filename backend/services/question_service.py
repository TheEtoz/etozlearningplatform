"""Database operations for the question bank and admin CRUD."""

from pydantic import ValidationError
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from backend.models.question import Question
from backend.models.topic import Topic
from backend.schemas.question import QuestionCreate, QuestionUpdate
from backend.services.topic_service import get_or_create_topics


class QuestionServiceError(ValueError):
    """Raised for admin question operations that cannot complete."""


def list_questions(
    database: Session,
    *,
    subject: str | None = None,
    topic: str | None = None,
    difficulty: str | None = None,
    question_type: str | None = None,
    search: str | None = None,
    visibility: str | None = None,
    viewer_id: int | None = None,
    owner_only: bool = False,
    offset: int = 0,
    limit: int = 50,
) -> list[Question]:
    """Return filtered bank questions with topic tags loaded.

    When ``viewer_id`` is set (teacher bank), only public questions and the
    viewer's own private questions are returned.
    """

    from backend.models.subject import Subject

    statement = select(Question).options(
        selectinload(Question.topic_tags).selectinload(Topic.subject)
    )

    if viewer_id is not None:
        if owner_only:
            statement = statement.where(Question.owner_id == viewer_id)
        else:
            statement = statement.where(
                or_(
                    Question.visibility == "public",
                    Question.owner_id == viewer_id,
                )
            )
    if subject:
        statement = statement.where(
            Question.topic_tags.any(
                Topic.subject.has(Subject.name == subject.strip().lower())
            )
        )
    if topic:
        statement = statement.where(
            Question.topic_tags.any(Topic.name == topic.strip().lower())
        )
    if difficulty:
        statement = statement.where(Question.difficulty == difficulty)
    if question_type:
        statement = statement.where(Question.type == question_type)
    if visibility:
        statement = statement.where(Question.visibility == visibility)
    if search:
        pattern = f"%{search.strip()}%"
        statement = statement.where(
            or_(
                Question.title.ilike(pattern),
                Question.description.ilike(pattern),
            )
        )

    statement = statement.order_by(Question.id).offset(offset).limit(limit)
    return list(database.scalars(statement).unique().all())


def get_question(database: Session, question_id: int) -> Question | None:
    """Return one question with topics loaded."""

    statement = (
        select(Question)
        .options(selectinload(Question.topic_tags).selectinload(Topic.subject))
        .where(Question.id == question_id)
    )
    return database.scalars(statement).unique().first()


def actor_can_use_question(question: Question, actor_id: int) -> bool:
    """Teachers may attach public/legacy questions or their own private ones."""

    if question.visibility != "private":
        return True
    return question.owner_id in (None, actor_id)


def question_subject_name(question: Question) -> str:
    """Subject name from the first linked area."""

    for tag in question.topic_tags or []:
        if tag.subject is not None:
            return tag.subject.name
    return "python"


def check_mcq_answer(
    database: Session,
    question_id: int,
    selected_answer: str,
) -> dict[str, object] | None:
    """Compare a selected MCQ answer and return learning feedback."""

    question = get_question(database, question_id)
    if question is None or question.type != "mcq":
        return None

    selected = selected_answer.strip()
    correct = (question.correct_answer or "").strip()
    is_correct = selected == correct

    if is_correct:
        explanation = "Correct. Nice work — keep going."
    else:
        explanation = (
            f"Not quite. The correct answer is **{correct}**. "
            "Review the question and try a similar one next."
        )

    return {
        "is_correct": is_correct,
        "selected_answer": selected,
        "correct_answer": correct,
        "explanation": explanation,
    }


def create_question(
    database: Session,
    payload: QuestionCreate,
    *,
    owner_id: int | None = None,
) -> Question:
    """Insert a teacher-authored bank question with topic tags."""

    topics = get_or_create_topics(
        database, payload.topics, subject=payload.subject
    )
    if not topics:
        raise QuestionServiceError("At least one area is required")

    visibility = getattr(payload, "visibility", None)
    visibility_value = (
        visibility.value if hasattr(visibility, "value") else (visibility or "public")
    )

    question = Question(
        title=payload.title.strip(),
        description=payload.description.strip(),
        difficulty=payload.difficulty.value,
        type=payload.type.value,
        topic=topics[0].name,
        language=payload.language.strip() or "python",
        owner_id=owner_id,
        visibility=visibility_value,
        choices=payload.choices,
        correct_answer=payload.correct_answer,
        starter_code=payload.starter_code,
        test_cases=payload.test_cases,
        topic_tags=topics,
    )
    database.add(question)
    database.commit()
    return get_question(database, question.id)  # type: ignore[return-value]


def update_question(
    database: Session,
    question_id: int,
    payload: QuestionUpdate,
    *,
    actor_id: int | None = None,
) -> Question:
    """Apply a partial update, then re-validate type-specific fields."""

    question = get_question(database, question_id)
    if question is None:
        raise QuestionServiceError("Question not found")
    # Admin/teacher routes already gate access. Any teacher may fix bank items
    # (including seeded or another teacher's shared drafts) so classrooms are not stuck.

    updates = payload.model_dump(exclude_unset=True)
    topic_names = updates.pop("topics", None)
    subject_name = updates.pop("subject", None)
    if "difficulty" in updates and updates["difficulty"] is not None:
        updates["difficulty"] = updates["difficulty"].value
    if "type" in updates and updates["type"] is not None:
        updates["type"] = updates["type"].value
    if "visibility" in updates and updates["visibility"] is not None:
        updates["visibility"] = updates["visibility"].value

    for field, value in updates.items():
        setattr(question, field, value)

    resolved_subject = (
        subject_name.strip().lower()
        if isinstance(subject_name, str) and subject_name.strip()
        else question_subject_name(question)
    )
    if topic_names is not None:
        topics = get_or_create_topics(
            database, topic_names, subject=resolved_subject
        )
        if not topics:
            raise QuestionServiceError("At least one area is required")
        question.topic_tags = topics
        question.topic = topics[0].name

    try:
        QuestionCreate(
            title=question.title,
            description=question.description,
            difficulty=question.difficulty,
            type=question.type,
            subject=resolved_subject,
            topics=question.topics or ["general"],
            language=question.language,
            visibility=question.visibility or "public",
            choices=question.choices,
            correct_answer=question.correct_answer,
            starter_code=question.starter_code,
            test_cases=question.test_cases,
        )
    except ValidationError:
        database.rollback()
        raise

    database.commit()
    refreshed = get_question(database, question_id)
    if refreshed is None:
        raise QuestionServiceError("Question not found")
    return refreshed


def clone_question(
    database: Session,
    question_id: int,
    *,
    owner_id: int,
    title_suffix: str = " (copy)",
    commit: bool = True,
) -> Question:
    """Copy a bank question for quiz-local customization (does not alter original)."""

    source = get_question(database, question_id)
    if source is None:
        raise QuestionServiceError("Question not found")
    if source.visibility == "private" and source.owner_id not in (None, owner_id):
        raise QuestionServiceError("Cannot customize a private question you do not own")

    subject = question_subject_name(source)
    areas = source.topics or ["general"]
    topics = get_or_create_topics(database, areas, subject=subject)
    clone = Question(
        title=(source.title + title_suffix)[:200],
        description=source.description,
        difficulty=source.difficulty,
        type=source.type,
        topic=topics[0].name if topics else source.topic,
        language=source.language,
        owner_id=owner_id,
        visibility="private",
        choices=list(source.choices) if source.choices else None,
        correct_answer=source.correct_answer,
        starter_code=source.starter_code,
        test_cases=(
            [dict(case) for case in source.test_cases]
            if source.test_cases
            else None
        ),
        topic_tags=topics,
    )
    database.add(clone)
    if commit:
        database.commit()
        refreshed = get_question(database, clone.id)
        if refreshed is None:
            raise QuestionServiceError("Clone failed")
        return refreshed
    database.flush()
    return clone


def delete_question(
    database: Session,
    question_id: int,
    *,
    actor_id: int | None = None,
) -> None:
    """Delete a bank question when the actor owns it and no submissions exist."""

    question = get_question(database, question_id)
    if question is None:
        raise QuestionServiceError("Question not found")
    if actor_id is not None:
        if question.owner_id is None:
            raise QuestionServiceError(
                "This shared question has no author on record and cannot be deleted"
            )
        if question.owner_id != actor_id:
            raise QuestionServiceError("Only the author can delete this question")

    try:
        database.delete(question)
        database.commit()
    except IntegrityError as error:
        database.rollback()
        raise QuestionServiceError(
            "Cannot delete a question that already has student submissions"
        ) from error


def question_to_student_dict(question: Question) -> dict:
    """Serialize a bank question for student-facing responses."""

    return {
        "id": question.id,
        "title": question.title,
        "description": question.description,
        "difficulty": question.difficulty,
        "type": question.type,
        "subject": question_subject_name(question),
        "topics": question.topics,
        "language": question.language,
        "choices": question.choices,
        "starter_code": question.starter_code,
        "created_at": question.created_at,
    }


def question_to_admin_dict(
    question: Question,
    *,
    actor_id: int | None = None,
) -> dict:
    """Serialize a bank question for teachers (includes answers/tests)."""

    payload = question_to_student_dict(question)
    payload["correct_answer"] = question.correct_answer
    payload["test_cases"] = question.test_cases
    payload["owner_id"] = question.owner_id
    payload["visibility"] = question.visibility
    is_owner = actor_id is not None and question.owner_id == actor_id
    # Teachers using the admin bank can edit any listed question.
    payload["can_edit"] = actor_id is not None or question.owner_id is None
    payload["can_delete"] = is_owner
    return payload

