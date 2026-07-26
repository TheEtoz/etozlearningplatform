"""Per-topic learning-progress database model."""

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base

if TYPE_CHECKING:
    from backend.models.user import User


class Progress(Base):
    """Aggregated performance for one user and topic."""

    __tablename__ = "progress"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "topic",
            name="uq_progress_user_topic",
        ),
        CheckConstraint(
            "questions_attempted >= 0",
            name="attempted_non_negative",
        ),
        CheckConstraint(
            "questions_correct >= 0 "
            "AND questions_correct <= questions_attempted",
            name="correct_valid",
        ),
        CheckConstraint(
            "accuracy >= 0 AND accuracy <= 100",
            name="accuracy_range",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    topic: Mapped[str] = mapped_column(String(100), index=True)
    questions_attempted: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
    )
    questions_correct: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
    )
    accuracy: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        default=Decimal("0.00"),
        server_default="0.00",
    )

    user: Mapped["User"] = relationship(back_populates="progress_records")
