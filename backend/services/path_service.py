"""Coding-path modules and free-jump levels."""

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.models.coding_module import CodingModule, ModuleLevel
from backend.models.question import Question
from backend.models.submission import Submission
from backend.schemas.path import ModuleCreate, ModuleUpdate


class PathServiceError(ValueError):
    """Raised for coding-path admin operations that cannot complete."""


def list_modules(database: Session) -> list[CodingModule]:
    """Return modules with ordered levels and questions."""

    statement = (
        select(CodingModule)
        .options(
            selectinload(CodingModule.levels)
            .selectinload(ModuleLevel.question)
            .selectinload(Question.topic_tags)
        )
        .order_by(CodingModule.position, CodingModule.id)
    )
    return list(database.scalars(statement).unique().all())


def get_module(database: Session, module_id: int) -> CodingModule | None:
    """Return one module with levels loaded."""

    statement = (
        select(CodingModule)
        .options(
            selectinload(CodingModule.levels)
            .selectinload(ModuleLevel.question)
            .selectinload(Question.topic_tags)
        )
        .where(CodingModule.id == module_id)
    )
    return database.scalars(statement).unique().first()


def completed_question_ids(database: Session, user_id: int) -> set[int]:
    """Question ids the student has fully passed at least once."""

    rows = database.scalars(
        select(Submission.question_id).where(
            Submission.user_id == user_id,
            Submission.status == "passed",
        )
    ).all()
    return set(rows)


def build_path_for_user(database: Session, user_id: int) -> list[dict]:
    """Serialize the free-jump coding path with completion flags."""

    done = completed_question_ids(database, user_id)
    payload: list[dict] = []
    for module in list_modules(database):
        levels = []
        for level in module.levels:
            question = level.question
            if question is None or question.type != "coding":
                continue
            levels.append(
                {
                    "level_id": level.id,
                    "position": level.position,
                    "question_id": question.id,
                    "title": question.title,
                    "difficulty": question.difficulty,
                    "topics": question.topics,
                    "is_completed": question.id in done,
                }
            )
        payload.append(
            {
                "id": module.id,
                "title": module.title,
                "description": module.description,
                "position": module.position,
                "difficulty_label": module.difficulty_label,
                "levels": levels,
                "completed_count": sum(1 for item in levels if item["is_completed"]),
                "total_count": len(levels),
            }
        )
    return payload


def create_module(database: Session, payload: ModuleCreate) -> CodingModule:
    """Create a coding-path module."""

    existing = database.scalars(
        select(CodingModule).where(CodingModule.title == payload.title.strip())
    ).first()
    if existing is not None:
        raise PathServiceError("A module with this title already exists")

    module = CodingModule(
        title=payload.title.strip(),
        description=payload.description.strip(),
        position=payload.position,
        difficulty_label=payload.difficulty_label,
    )
    database.add(module)
    database.commit()
    refreshed = get_module(database, module.id)
    if refreshed is None:
        raise PathServiceError("Module not found after create")
    return refreshed


def update_module(
    database: Session,
    module_id: int,
    payload: ModuleUpdate,
) -> CodingModule:
    """Update module metadata."""

    module = get_module(database, module_id)
    if module is None:
        raise PathServiceError("Module not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(module, field, value)
    database.commit()
    refreshed = get_module(database, module_id)
    if refreshed is None:
        raise PathServiceError("Module not found")
    return refreshed


def delete_module(database: Session, module_id: int) -> None:
    """Delete a module and its levels."""

    module = get_module(database, module_id)
    if module is None:
        raise PathServiceError("Module not found")
    database.delete(module)
    database.commit()


def set_module_levels(
    database: Session,
    module_id: int,
    question_ids: list[int],
) -> CodingModule:
    """Replace ordered coding levels for a module."""

    module = get_module(database, module_id)
    if module is None:
        raise PathServiceError("Module not found")

    if len(question_ids) != len(set(question_ids)):
        raise PathServiceError("Duplicate question ids are not allowed")

    for question_id in question_ids:
        question = database.get(Question, question_id)
        if question is None:
            raise PathServiceError(f"Question {question_id} not found")
        if question.type != "coding":
            raise PathServiceError(
                f"Question {question_id} must be a coding question"
            )

    for level in list(module.levels):
        database.delete(level)
    database.flush()
    for position, question_id in enumerate(question_ids):
        database.add(
            ModuleLevel(
                module_id=module.id,
                question_id=question_id,
                position=position,
            )
        )
    database.commit()
    database.expire_all()
    refreshed = get_module(database, module_id)
    if refreshed is None:
        raise PathServiceError("Module not found")
    return refreshed
