"""Persisted student quiz attempts for scores and future statistics."""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base

if TYPE_CHECKING:
    from backend.models.quiz import Quiz
    from backend.models.user import User


class QuizAttempt(Base):
    """One completed attempt of a quiz by a student.

    Students may redo quizzes. Each redo creates a new attempt row so score
    history remains available for statistics.
    """

    __tablename__ = "quiz_attempts"
    __table_args__ = (
        CheckConstraint(
            "questions_answered >= 0 "
            "AND questions_answered <= questions_total",
            name="answered_valid",
        ),
        CheckConstraint(
            "questions_correct >= 0 "
            "AND questions_correct <= questions_answered",
            name="correct_valid",
        ),
        CheckConstraint(
            "score >= 0 AND score <= 100",
            name="score_range",
        ),
        CheckConstraint(
            "status IN ('completed')",
            name="valid_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    quiz_id: Mapped[int] = mapped_column(
        ForeignKey("quizzes.id", ondelete="CASCADE"),
        index=True,
    )
    questions_total: Mapped[int] = mapped_column(Integer)
    questions_answered: Mapped[int] = mapped_column(Integer)
    questions_correct: Mapped[int] = mapped_column(Integer)
    score: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    status: Mapped[str] = mapped_column(
        String(20),
        default="completed",
        server_default="completed",
    )
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
    )

    user: Mapped["User"] = relationship(back_populates="quiz_attempts")
    quiz: Mapped["Quiz"] = relationship(back_populates="attempts")
