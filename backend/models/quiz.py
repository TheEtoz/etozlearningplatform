"""Teacher-designed quiz packs for student practice."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base

if TYPE_CHECKING:
    from backend.models.question import Question
    from backend.models.quiz_attempt import QuizAttempt
    from backend.models.quiz_question import QuizQuestion


class Quiz(Base):
    """A curated set of bank questions with an optional teacher-set timer."""

    __tablename__ = "quizzes"
    __table_args__ = (
        CheckConstraint(
            "(is_timed = false AND duration_seconds IS NULL) OR "
            "(is_timed = true AND duration_seconds > 0)",
            name="timed_duration_valid",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text)
    # Optional label; topics are derived from contained questions.
    topic: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    is_timed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
    )
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    quiz_questions: Mapped[list["QuizQuestion"]] = relationship(
        back_populates="quiz",
        cascade="all, delete-orphan",
        order_by="QuizQuestion.position",
        passive_deletes=True,
    )
    attempts: Mapped[list["QuizAttempt"]] = relationship(
        back_populates="quiz",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @property
    def questions(self) -> list["Question"]:
        """Ordered bank questions attached to this quiz."""

        return [link.question for link in self.quiz_questions]
