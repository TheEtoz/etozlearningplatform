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
    topic: str | None = None,
    difficulty: str | None = None,
    question_type: str | None = None,
    search: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[Question]:
    """Return filtered bank questions with topic tags loaded."""

    statement = select(Question).options(selectinload(Question.topic_tags))

    if topic:
        statement = statement.where(
            Question.topic_tags.any(Topic.name == topic.strip().lower())
        )
    if difficulty:
        statement = statement.where(Question.difficulty == difficulty)
    if question_type:
        statement = statement.where(Question.type == question_type)
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
        .options(selectinload(Question.topic_tags))
        .where(Question.id == question_id)
    )
    return database.scalars(statement).unique().first()


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


def create_question(database: Session, payload: QuestionCreate) -> Question:
    """Insert a teacher-authored bank question with topic tags."""

    topics = get_or_create_topics(database, payload.topics)
    if not topics:
        raise QuestionServiceError("At least one topic is required")

    question = Question(
        title=payload.title.strip(),
        description=payload.description.strip(),
        difficulty=payload.difficulty.value,
        type=payload.type.value,
        topic=topics[0].name,
        language=payload.language.strip() or "python",
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
) -> Question:
    """Apply a partial update, then re-validate type-specific fields."""

    question = get_question(database, question_id)
    if question is None:
        raise QuestionServiceError("Question not found")

    updates = payload.model_dump(exclude_unset=True)
    topic_names = updates.pop("topics", None)
    if "difficulty" in updates and updates["difficulty"] is not None:
        updates["difficulty"] = updates["difficulty"].value
    if "type" in updates and updates["type"] is not None:
        updates["type"] = updates["type"].value

    for field, value in updates.items():
        setattr(question, field, value)

    if topic_names is not None:
        topics = get_or_create_topics(database, topic_names)
        if not topics:
            raise QuestionServiceError("At least one topic is required")
        question.topic_tags = topics
        question.topic = topics[0].name

    try:
        QuestionCreate(
            title=question.title,
            description=question.description,
            difficulty=question.difficulty,
            type=question.type,
            topics=question.topics or ["general"],
            language=question.language,
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


def delete_question(database: Session, question_id: int) -> None:
    """Delete a bank question when no submissions reference it."""

    question = get_question(database, question_id)
    if question is None:
        raise QuestionServiceError("Question not found")

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
        "topics": question.topics,
        "language": question.language,
        "choices": question.choices,
        "starter_code": question.starter_code,
        "created_at": question.created_at,
    }


def question_to_admin_dict(question: Question) -> dict:
    """Serialize a bank question for teachers (includes answers/tests)."""

    payload = question_to_student_dict(question)
    payload["correct_answer"] = question.correct_answer
    payload["test_cases"] = question.test_cases
    return payload
