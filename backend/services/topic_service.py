"""Helpers for subjects and areas (topics) inside them."""

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.models.subject import Subject
from backend.models.topic import Topic

DEFAULT_SUBJECTS = ("python", "math", "java")


def ensure_default_subjects(database: Session) -> None:
    """Seed the common subject tracks if the table is empty/missing them."""

    for name in DEFAULT_SUBJECTS:
        get_or_create_subject(database, name)
    database.commit()


def list_subjects(database: Session) -> list[Subject]:
    """Return subjects with nested areas."""

    return list(
        database.scalars(
            select(Subject)
            .options(selectinload(Subject.areas))
            .order_by(Subject.name)
        ).unique().all()
    )


def get_or_create_subject(database: Session, name: str) -> Subject:
    """Resolve a subject name to a row, creating it if needed."""

    cleaned = name.strip().lower()
    if not cleaned:
        raise ValueError("Subject name is required")
    subject = database.scalars(
        select(Subject).where(Subject.name == cleaned)
    ).first()
    if subject is None:
        subject = Subject(name=cleaned)
        database.add(subject)
        database.flush()
    return subject


def list_topics(database: Session, *, subject: str | None = None) -> list[Topic]:
    """Return areas, optionally filtered by subject name."""

    statement = select(Topic).options(selectinload(Topic.subject)).order_by(Topic.name)
    if subject:
        statement = statement.join(Subject).where(
            Subject.name == subject.strip().lower()
        )
    return list(database.scalars(statement).unique().all())


def get_or_create_topics(
    database: Session,
    names: list[str],
    *,
    subject: str | None = None,
) -> list[Topic]:
    """Resolve area names under a subject (default: python)."""

    subject_row = get_or_create_subject(database, subject or "python")
    topics: list[Topic] = []
    for raw in names:
        name = raw.strip().lower()
        if not name:
            continue
        topic = database.scalars(
            select(Topic).where(
                Topic.subject_id == subject_row.id,
                Topic.name == name,
            )
        ).first()
        if topic is None:
            topic = Topic(name=name, subject_id=subject_row.id)
            database.add(topic)
            database.flush()
        topics.append(topic)
    return topics


def subject_tree(database: Session) -> list[dict]:
    """Serialize subjects with their areas for the teacher UI."""

    ensure_default_subjects(database)
    payload = []
    for subject in list_subjects(database):
        payload.append(
            {
                "id": subject.id,
                "name": subject.name,
                "areas": [
                    {"id": area.id, "name": area.name} for area in subject.areas
                ],
            }
        )
    return payload
