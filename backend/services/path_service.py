"""Class learning-path modules and ordered content blocks."""

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.models.classroom import ClassModule, Classroom
from backend.models.coding_module import CodingModule, ModuleBlock
from backend.models.question import Question
from backend.schemas.path import ModuleBlockCreate, ModuleCreate, ModuleUpdate


class PathServiceError(ValueError):
    """Raised for coding-path admin operations that cannot complete."""


def _module_load_options():
    return (
        selectinload(CodingModule.blocks)
        .selectinload(ModuleBlock.question)
        .selectinload(Question.topic_tags)
    )


def _require_class_owner(
    database: Session,
    class_id: int,
    *,
    actor_id: int,
) -> Classroom:
    classroom = database.get(Classroom, class_id)
    if classroom is None:
        raise PathServiceError("Class not found")
    if classroom.owner_id != actor_id:
        raise PathServiceError("Only the class owner can manage this module")
    return classroom


def _require_module_owner(
    database: Session,
    module: CodingModule,
    *,
    actor_id: int,
) -> Classroom:
    return _require_class_owner(database, module.class_id, actor_id=actor_id)


def list_modules(
    database: Session,
    *,
    class_id: int | None = None,
    owner_id: int | None = None,
) -> list[CodingModule]:
    """Return modules with ordered blocks, optionally filtered by class/owner."""

    statement = (
        select(CodingModule)
        .options(_module_load_options())
        .order_by(CodingModule.position, CodingModule.id)
    )
    if class_id is not None:
        if owner_id is not None:
            _require_class_owner(database, class_id, actor_id=owner_id)
        statement = statement.where(CodingModule.class_id == class_id)
    elif owner_id is not None:
        statement = statement.join(
            Classroom, CodingModule.class_id == Classroom.id
        ).where(Classroom.owner_id == owner_id)
    return list(database.scalars(statement).unique().all())


def get_module(
    database: Session,
    module_id: int,
    *,
    actor_id: int | None = None,
) -> CodingModule | None:
    """Return one module with blocks loaded."""

    statement = (
        select(CodingModule)
        .options(_module_load_options())
        .where(CodingModule.id == module_id)
    )
    module = database.scalars(statement).unique().first()
    if module is not None and actor_id is not None:
        _require_module_owner(database, module, actor_id=actor_id)
    return module


def build_path_for_user(database: Session, user_id: int) -> list[dict]:
    """Legacy global path — empty; students use class-scoped paths."""

    del database, user_id
    return []


def _next_module_position(database: Session, class_id: int) -> int:
    """Return the next free append position for a class path."""

    link_positions = list(
        database.scalars(
            select(ClassModule.position).where(ClassModule.class_id == class_id)
        ).all()
    )
    module_positions = list(
        database.scalars(
            select(CodingModule.position).where(CodingModule.class_id == class_id)
        ).all()
    )
    all_positions = link_positions + module_positions
    return (max(all_positions) + 1) if all_positions else 0


def _make_room_at_position(
    database: Session,
    class_id: int,
    position: int,
    *,
    exclude_module_id: int | None = None,
) -> None:
    """Shift later modules/links up so ``position`` is free (desc to avoid clashes)."""

    link_query = select(ClassModule).where(
        ClassModule.class_id == class_id,
        ClassModule.position >= position,
    )
    if exclude_module_id is not None:
        link_query = link_query.where(ClassModule.module_id != exclude_module_id)
    links = list(
        database.scalars(link_query.order_by(ClassModule.position.desc())).all()
    )
    for link in links:
        link.position += 1

    module_query = select(CodingModule).where(
        CodingModule.class_id == class_id,
        CodingModule.position >= position,
    )
    if exclude_module_id is not None:
        module_query = module_query.where(CodingModule.id != exclude_module_id)
    modules = list(
        database.scalars(module_query.order_by(CodingModule.position.desc())).all()
    )
    for module in modules:
        module.position += 1
    database.flush()


def _ensure_class_module_link(
    database: Session,
    *,
    class_id: int,
    module_id: int,
    position: int,
) -> None:
    link = database.scalars(
        select(ClassModule).where(
            ClassModule.class_id == class_id,
            ClassModule.module_id == module_id,
        )
    ).first()
    clash = database.scalars(
        select(ClassModule).where(
            ClassModule.class_id == class_id,
            ClassModule.position == position,
            ClassModule.module_id != module_id,
        )
    ).first()
    if clash is not None:
        _make_room_at_position(
            database,
            class_id,
            position,
            exclude_module_id=module_id,
        )

    if link is None:
        database.add(
            ClassModule(
                class_id=class_id,
                module_id=module_id,
                position=position,
                is_published=True,
            )
        )
    else:
        link.position = position
        link.is_published = True


def create_module(
    database: Session,
    payload: ModuleCreate,
    *,
    actor_id: int | None = None,
) -> CodingModule:
    """Create a module inside a class, optionally with an initial lecture block."""

    if actor_id is not None:
        _require_class_owner(database, payload.class_id, actor_id=actor_id)
    else:
        classroom = database.get(Classroom, payload.class_id)
        if classroom is None:
            raise PathServiceError("Class not found")

    title = payload.title.strip()
    existing = database.scalars(
        select(CodingModule).where(
            CodingModule.class_id == payload.class_id,
            CodingModule.title == title,
        )
    ).first()
    if existing is not None:
        raise PathServiceError("A module with this title already exists in the class")

    # Prefer requested order; if taken, append at the end (reorder with ↑↓).
    requested = max(0, int(payload.position))
    position_taken = database.scalars(
        select(ClassModule.id).where(
            ClassModule.class_id == payload.class_id,
            ClassModule.position == requested,
        )
    ).first()
    position = (
        requested
        if position_taken is None
        else _next_module_position(database, payload.class_id)
    )

    module = CodingModule(
        class_id=payload.class_id,
        title=title,
        description=payload.description.strip(),
        position=position,
        difficulty_label=payload.difficulty_label,
    )
    database.add(module)
    database.flush()
    # Every module starts with a lecture block so teachers write content first.
    database.add(
        ModuleBlock(
            module_id=module.id,
            position=0,
            type="lecture",
            payload={"markdown": payload.description.strip()},
        )
    )
    _ensure_class_module_link(
        database,
        class_id=payload.class_id,
        module_id=module.id,
        position=position,
    )
    database.commit()
    refreshed = get_module(database, module.id)
    if refreshed is None:
        raise PathServiceError("Module not found after create")
    return refreshed


def update_module(
    database: Session,
    module_id: int,
    payload: ModuleUpdate,
    *,
    actor_id: int | None = None,
) -> CodingModule:
    """Update module metadata."""

    module = get_module(database, module_id)
    if module is None:
        raise PathServiceError("Module not found")
    if actor_id is not None:
        _require_module_owner(database, module, actor_id=actor_id)

    updates = payload.model_dump(exclude_unset=True)
    if "title" in updates and updates["title"] is not None:
        title = updates["title"].strip()
        clash = database.scalars(
            select(CodingModule).where(
                CodingModule.class_id == module.class_id,
                CodingModule.title == title,
                CodingModule.id != module.id,
            )
        ).first()
        if clash is not None:
            raise PathServiceError(
                "A module with this title already exists in the class"
            )
        updates["title"] = title
    if "description" in updates and updates["description"] is not None:
        updates["description"] = updates["description"].strip()

    for field, value in updates.items():
        setattr(module, field, value)

    if "position" in updates:
        _ensure_class_module_link(
            database,
            class_id=module.class_id,
            module_id=module.id,
            position=int(updates["position"]),
        )

    database.commit()
    refreshed = get_module(database, module_id)
    if refreshed is None:
        raise PathServiceError("Module not found")
    return refreshed


def delete_module(
    database: Session,
    module_id: int,
    *,
    actor_id: int | None = None,
) -> None:
    module = get_module(database, module_id)
    if module is None:
        raise PathServiceError("Module not found")
    if actor_id is not None:
        _require_module_owner(database, module, actor_id=actor_id)
    database.delete(module)
    database.commit()


def set_module_blocks(
    database: Session,
    module_id: int,
    blocks: list[ModuleBlockCreate],
    *,
    actor_id: int | None = None,
) -> CodingModule:
    """Replace ordered content blocks for a module."""

    from backend.services.question_service import actor_can_use_question

    module = get_module(database, module_id)
    if module is None:
        raise PathServiceError("Module not found")
    if actor_id is not None:
        _require_module_owner(database, module, actor_id=actor_id)

    for block in blocks:
        if block.type in ("mcq", "coding"):
            if block.question_id is None:
                raise PathServiceError(
                    f"{block.type} blocks require a question_id"
                )
            question = database.get(Question, block.question_id)
            if question is None:
                raise PathServiceError(f"Question {block.question_id} not found")
            if actor_id is not None and not actor_can_use_question(
                question, actor_id
            ):
                raise PathServiceError(
                    f"Cannot attach private question {block.question_id} "
                    "you do not own"
                )
            if block.type == "coding" and question.type != "coding":
                raise PathServiceError(
                    f"Question {block.question_id} must be a coding question"
                )
            if block.type == "mcq" and question.type != "mcq":
                raise PathServiceError(
                    f"Question {block.question_id} must be an MCQ"
                )

    for existing in list(module.blocks):
        database.delete(existing)
    database.flush()
    for position, block in enumerate(blocks):
        database.add(
            ModuleBlock(
                module_id=module.id,
                position=position,
                type=block.type,
                payload=dict(block.payload or {}),
                question_id=block.question_id,
            )
        )
    # Keep legacy description in sync with first lecture block.
    lecture = next((b for b in blocks if b.type == "lecture"), None)
    if lecture is not None:
        module.description = str((lecture.payload or {}).get("markdown") or "")
    database.commit()
    database.expire_all()
    refreshed = get_module(database, module_id)
    if refreshed is None:
        raise PathServiceError("Module not found")
    return refreshed


def set_module_levels(
    database: Session,
    module_id: int,
    question_ids: list[int],
    *,
    actor_id: int | None = None,
) -> CodingModule:
    """Legacy helper: set coding blocks from question ids, keep other blocks."""

    module = get_module(database, module_id)
    if module is None:
        raise PathServiceError("Module not found")

    kept = [
        ModuleBlockCreate(
            type=block.type,  # type: ignore[arg-type]
            payload=dict(block.payload or {}),
            question_id=block.question_id,
        )
        for block in module.blocks
        if block.type != "coding"
    ]
    for question_id in question_ids:
        kept.append(
            ModuleBlockCreate(type="coding", payload={}, question_id=question_id)
        )
    return set_module_blocks(
        database, module_id, kept, actor_id=actor_id
    )


def module_to_admin_dict(module: CodingModule) -> dict:
    coding_ids = [
        block.question_id
        for block in module.blocks
        if block.type == "coding" and block.question_id is not None
    ]
    return {
        "id": module.id,
        "class_id": module.class_id,
        "title": module.title,
        "description": module.description,
        "position": module.position,
        "difficulty_label": module.difficulty_label,
        "question_ids": coding_ids,
        "blocks": [
            {
                "id": block.id,
                "position": block.position,
                "type": block.type,
                "payload": block.payload or {},
                "question_id": block.question_id,
            }
            for block in module.blocks
        ],
    }


def serialize_module_for_student(
    module: CodingModule,
    *,
    done_question_ids: set[int],
) -> dict:
    blocks_payload = []
    coding_blocks = []
    for block in module.blocks:
        question = block.question
        item = {
            "id": block.id,
            "position": block.position,
            "type": block.type,
            "payload": block.payload or {},
            "question_id": block.question_id,
            "title": question.title if question else None,
            "description": question.description if question else "",
            "difficulty": question.difficulty if question else None,
            "topics": question.topics if question else [],
            "choices": question.choices if question else None,
            "starter_code": (question.starter_code or "") if question else "",
            "is_completed": bool(
                block.question_id and block.question_id in done_question_ids
            ),
        }
        if block.type in ("lecture", "text") and not item["payload"]:
            item["payload"] = {"markdown": module.description or ""}
        blocks_payload.append(item)
        if block.type == "coding":
            coding_blocks.append(item)

    coding_done = sum(1 for item in coding_blocks if item["is_completed"])
    return {
        "id": module.id,
        "title": module.title,
        "description": module.description,
        "position": module.position,
        "difficulty_label": module.difficulty_label,
        "blocks": blocks_payload,
        "levels": coding_blocks,
        "completed_count": coding_done,
        "total_count": len(coding_blocks),
    }
