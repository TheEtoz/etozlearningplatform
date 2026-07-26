"""Ordered membership of bank questions inside a quiz."""

from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class QuizQuestion(Base):
    """Attach a question-bank item to a quiz at a stable position."""

    __tablename__ = "quiz_questions"
    __table_args__ = (
        UniqueConstraint(
            "quiz_id",
            "question_id",
            name="uq_quiz_questions_quiz_question",
        ),
        UniqueConstraint(
            "quiz_id",
            "position",
            name="uq_quiz_questions_quiz_position",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    quiz_id: Mapped[int] = mapped_column(
        ForeignKey("quizzes.id", ondelete="CASCADE"),
        index=True,
    )
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"),
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, default=0)

    quiz = relationship("Quiz", back_populates="quiz_questions")
    question = relationship("Question", back_populates="quiz_links")
