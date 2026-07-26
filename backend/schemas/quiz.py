"""API schemas for teacher-designed quizzes."""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import Self


class QuizCardResponse(BaseModel):
    """Catalog card shown before a student starts a quiz."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    topics: list[str] = Field(default_factory=list)
    is_timed: bool
    duration_seconds: int | None = None
    question_count: int = Field(ge=0)
    difficulties: list[str] = Field(default_factory=list)
    question_types: list[str] = Field(default_factory=list)
    is_completed: bool = False
    attempt_count: int = Field(default=0, ge=0)
    best_score: Decimal | None = None
    last_score: Decimal | None = None


class QuizCreate(BaseModel):
    """Teacher input for a new quiz shell."""

    title: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=1, max_length=10_000)
    is_timed: bool = False
    duration_seconds: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_timer(self) -> Self:
        if self.is_timed and self.duration_seconds is None:
            raise ValueError("Timed quizzes require duration_seconds")
        if not self.is_timed:
            self.duration_seconds = None
        return self


class QuizUpdate(BaseModel):
    """Partial quiz update."""

    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = Field(default=None, min_length=1, max_length=10_000)
    is_timed: bool | None = None
    duration_seconds: int | None = Field(default=None, gt=0)


class QuizMembershipUpdate(BaseModel):
    """Replace the ordered question list for a quiz."""

    question_ids: list[int] = Field(default_factory=list)


class QuizAdminResponse(BaseModel):
    """Teacher view of a quiz and its ordered bank question ids."""

    id: int
    title: str
    description: str
    is_timed: bool
    duration_seconds: int | None
    question_ids: list[int] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)


class QuizAnswerItem(BaseModel):
    """One response submitted when the quiz ends (MCQ answer or code)."""

    question_id: int = Field(gt=0)
    answer: str | None = Field(default=None, max_length=10_000)
    code: str | None = Field(default=None, max_length=50_000)


class QuizCompleteRequest(BaseModel):
    """All answers collected during a quiz attempt."""

    answers: list[QuizAnswerItem]


class QuizQuestionResult(BaseModel):
    """Per-question review revealed only after the quiz is finished."""

    question_id: int
    title: str
    description: str
    type: str
    selected_answer: str | None = None
    submitted_code: str | None = None
    correct_answer: str | None = None
    is_correct: bool
    skipped: bool
    score: int = 0


class QuizCompleteResponse(BaseModel):
    """Final score and answer key for a finished quiz."""

    quiz_id: int
    attempt_id: int
    questions_total: int
    questions_answered: int
    questions_correct: int
    score: Decimal
    is_completed: bool = True
    results: list[QuizQuestionResult]
