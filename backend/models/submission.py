"""Student-submission database model."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
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
    from backend.models.question import Question
    from backend.models.user import User


class Submission(Base):
    """One attempt by a user to answer a question."""

    __tablename__ = "submissions"
    __table_args__ = (
        CheckConstraint(
            "score >= 0 AND score <= 100",
            name="score_range",
        ),
        CheckConstraint(
            "status IN ('pending', 'passed', 'failed', 'error')",
            name="valid_status",
        ),
        CheckConstraint(
            "code IS NOT NULL OR answer IS NOT NULL",
            name="has_response",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="RESTRICT"),
        index=True,
    )
    code: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        server_default="pending",
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
    )

    user: Mapped["User"] = relationship(back_populates="submissions")
    question: Mapped["Question"] = relationship(back_populates="submissions")
