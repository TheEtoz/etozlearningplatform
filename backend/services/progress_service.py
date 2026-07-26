"""Helpers for reading and updating aggregated learning progress."""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.progress import Progress
from backend.schemas.progress import ProgressSummary

# Topics below this accuracy (with enough attempts) are flagged as weak.
WEAK_TOPIC_THRESHOLD = Decimal("70.00")
MIN_ATTEMPTS_FOR_WEAK = 1


def record_topic_attempt(
    database: Session,
    *,
    user_id: int,
    topic: str,
    questions_attempted: int,
    questions_correct: int,
) -> Progress:
    """Add attempt results into the user's topic progress row."""

    progress = database.scalars(
        select(Progress).where(
            Progress.user_id == user_id,
            Progress.topic == topic,
        )
    ).first()

    if progress is None:
        progress = Progress(
            user_id=user_id,
            topic=topic,
            questions_attempted=0,
            questions_correct=0,
            accuracy=Decimal("0.00"),
        )
        database.add(progress)

    progress.questions_attempted += questions_attempted
    progress.questions_correct += questions_correct
    if progress.questions_attempted > 0:
        progress.accuracy = (
            Decimal(progress.questions_correct)
            * Decimal("100")
            / Decimal(progress.questions_attempted)
        ).quantize(Decimal("0.01"))
    else:
        progress.accuracy = Decimal("0.00")

    return progress


def list_user_progress(database: Session, *, user_id: int) -> list[Progress]:
    """Return per-topic progress rows for one student (topic A–Z)."""

    statement = (
        select(Progress)
        .where(Progress.user_id == user_id)
        .order_by(Progress.topic.asc())
    )
    return list(database.scalars(statement).all())


def get_progress_summary(database: Session, *, user_id: int) -> ProgressSummary:
    """Aggregate Progress rows into dashboard totals and weak topics."""

    rows = list_user_progress(database, user_id=user_id)
    attempted = sum(row.questions_attempted for row in rows)
    correct = sum(row.questions_correct for row in rows)

    if attempted > 0:
        overall = (
            Decimal(correct) * Decimal("100") / Decimal(attempted)
        ).quantize(Decimal("0.01"))
    else:
        overall = Decimal("0.00")

    weak_topics = [
        row.topic
        for row in rows
        if row.questions_attempted >= MIN_ATTEMPTS_FOR_WEAK
        and row.accuracy < WEAK_TOPIC_THRESHOLD
    ]

    return ProgressSummary(
        questions_attempted=attempted,
        questions_correct=correct,
        overall_accuracy=overall,
        weak_topics=weak_topics,
    )
