"""Helpers for canonical topic tags."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.topic import Topic


def list_topics(database: Session) -> list[Topic]:
    """Return all topics sorted by name."""

    return list(database.scalars(select(Topic).order_by(Topic.name)).all())


def get_or_create_topics(database: Session, names: list[str]) -> list[Topic]:
    """Resolve topic names to Topic rows, creating missing ones."""

    topics: list[Topic] = []
    for raw in names:
        name = raw.strip().lower()
        if not name:
            continue
        topic = database.scalars(select(Topic).where(Topic.name == name)).first()
        if topic is None:
            topic = Topic(name=name)
            database.add(topic)
            database.flush()
        topics.append(topic)
    return topics
