"""Learning-question database model (question bank)."""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base
from backend.models.topic import question_topics

if TYPE_CHECKING:
    from backend.models.coding_module import ModuleLevel
    from backend.models.quiz_question import QuizQuestion
    from backend.models.submission import Submission
    from backend.models.topic import Topic


class Question(Base):
    """An MCQ or coding exercise in the shared question bank."""

    __tablename__ = "questions"
    __table_args__ = (
        CheckConstraint(
            "difficulty IN ('easy', 'medium', 'hard')",
            name="valid_difficulty",
        ),
        CheckConstraint(
            "type IN ('mcq', 'coding')",
            name="valid_type",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), index=True)
    description: Mapped[str] = mapped_column(Text)
    difficulty: Mapped[str] = mapped_column(String(20), index=True)
    type: Mapped[str] = mapped_column(String(20), index=True)
    # Legacy single-topic column kept nullable during/after migration.
    topic: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    language: Mapped[str] = mapped_column(
        String(50),
        default="python",
        server_default="python",
        index=True,
    )
    choices: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    correct_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    starter_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    test_cases: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    topic_tags: Mapped[list["Topic"]] = relationship(
        secondary=question_topics,
        back_populates="questions",
    )
    quiz_links: Mapped[list["QuizQuestion"]] = relationship(
        back_populates="question",
        cascade="all, delete-orphan",
    )
    module_levels: Mapped[list["ModuleLevel"]] = relationship(
        back_populates="question",
    )
    submissions: Mapped[list["Submission"]] = relationship(
        back_populates="question",
    )

    @property
    def topics(self) -> list[str]:
        """Convenience list of topic names for API responses."""

        return sorted(tag.name for tag in self.topic_tags)
