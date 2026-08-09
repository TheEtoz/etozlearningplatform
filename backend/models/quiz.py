"""Teacher-designed quiz packs for student practice."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base

if TYPE_CHECKING:
    from backend.models.classroom import ClassQuiz
    from backend.models.question import Question
    from backend.models.quiz_attempt import QuizAttempt
    from backend.models.quiz_question import QuizQuestion
    from backend.models.user import User


class Quiz(Base):
    """A curated set of bank questions with an optional teacher-set timer."""

    __tablename__ = "quizzes"
    __table_args__ = (
        CheckConstraint(
            "(is_timed = false AND duration_seconds IS NULL) OR "
            "(is_timed = true AND duration_seconds > 0)",
            name="timed_duration_valid",
        ),
        CheckConstraint(
            "visibility IN ('public', 'private')",
            name="valid_quiz_visibility",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    topic: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    is_timed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
    )
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    owner_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    visibility: Mapped[str] = mapped_column(
        String(20),
        default="public",
        server_default="public",
        index=True,
    )
    source_quiz_id: Mapped[int | None] = mapped_column(
        ForeignKey("quizzes.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    owner: Mapped["User | None"] = relationship(foreign_keys=[owner_id])
    source_quiz: Mapped["Quiz | None"] = relationship(
        remote_side=[id],
        foreign_keys=[source_quiz_id],
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
    class_links: Mapped[list["ClassQuiz"]] = relationship(
        back_populates="quiz",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    @property
    def questions(self) -> list["Question"]:
        """Ordered bank questions attached to this quiz."""

        return [link.question for link in self.quiz_questions]
