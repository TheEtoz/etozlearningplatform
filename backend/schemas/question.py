"""Validated API schemas for MCQ and coding questions."""

from datetime import datetime
from enum import Enum
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Difficulty(str, Enum):
    """Supported question difficulty levels."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class QuestionType(str, Enum):
    """Supported learning activity types."""

    MCQ = "mcq"
    CODING = "coding"


class QuestionVisibility(str, Enum):
    """Whether other teachers can reuse this bank question."""

    PUBLIC = "public"
    PRIVATE = "private"


class QuestionBase(BaseModel):
    """Fields shared by question creation and responses."""

    title: str = Field(min_length=3, max_length=200)
    description: str = Field(default="", max_length=10_000)
    difficulty: Difficulty
    type: QuestionType
    subject: str = Field(default="python", min_length=1, max_length=100)
    topics: list[str] = Field(min_length=1, description="Areas inside the subject")
    language: str = Field(default="python", min_length=1, max_length=50)


class QuestionCreate(QuestionBase):
    """Teacher input for creating a bank question."""

    visibility: QuestionVisibility = QuestionVisibility.PUBLIC
    choices: list[str] | None = None
    correct_answer: str | None = None
    starter_code: str | None = None
    test_cases: list[dict[str, Any]] | None = None

    @model_validator(mode="after")
    def validate_type_specific_fields(self) -> Self:
        """Require fields appropriate for the selected question type."""

        self.subject = self.subject.strip().lower()
        if not self.subject:
            raise ValueError("Subject is required")
        cleaned = [topic.strip().lower() for topic in self.topics if topic.strip()]
        if not cleaned:
            raise ValueError("At least one area inside the subject is required")
        self.topics = cleaned

        if self.type is QuestionType.MCQ:
            if not self.choices or len(self.choices) < 2:
                raise ValueError("MCQ questions require at least two choices")
            if len(set(self.choices)) != len(self.choices):
                raise ValueError("MCQ choices must be unique")
            if self.correct_answer not in self.choices:
                raise ValueError("correct_answer must match one of the choices")
            if self.test_cases:
                raise ValueError("MCQ questions cannot contain test cases")

        if self.type is QuestionType.CODING:
            if not self.test_cases:
                raise ValueError("Coding questions require at least one test case")
            if self.choices or self.correct_answer:
                raise ValueError(
                    "Coding questions cannot contain MCQ answers or choices"
                )

        return self


class QuestionUpdate(BaseModel):
    """Partial teacher update for an existing question."""

    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=10_000)
    difficulty: Difficulty | None = None
    type: QuestionType | None = None
    subject: str | None = Field(default=None, min_length=1, max_length=100)
    topics: list[str] | None = Field(default=None, min_length=1)
    language: str | None = Field(default=None, min_length=1, max_length=50)
    visibility: QuestionVisibility | None = None
    choices: list[str] | None = None
    correct_answer: str | None = None
    starter_code: str | None = None
    test_cases: list[dict[str, Any]] | None = None


class QuestionResponse(BaseModel):
    """Student-safe question data."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    difficulty: Difficulty
    type: QuestionType
    subject: str = "python"
    topics: list[str] = Field(default_factory=list)
    language: str
    choices: list[str] | None = None
    starter_code: str | None = None
    created_at: datetime


class QuestionAdminResponse(QuestionResponse):
    """Full question payload for teachers only."""

    correct_answer: str | None = None
    test_cases: list[dict[str, Any]] | None = None
    owner_id: int | None = None
    visibility: QuestionVisibility = QuestionVisibility.PUBLIC
    can_edit: bool = False
    can_delete: bool = False


class AnswerCheckRequest(BaseModel):
    """Student answer submitted for immediate learning feedback."""

    answer: str = Field(min_length=1, max_length=10_000)


class AnswerCheckResponse(BaseModel):
    """Feedback returned only after a student attempts a question."""

    is_correct: bool
    selected_answer: str
    correct_answer: str
    explanation: str


class TopicResponse(BaseModel):
    """Area (topic) inside a subject."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    subject_id: int | None = None
    subject: str | None = None


class AreaBrief(BaseModel):
    """Minimal area payload nested under a subject."""

    id: int
    name: str


class SubjectResponse(BaseModel):
    """Subject with nested areas."""

    id: int
    name: str
    areas: list[AreaBrief] = Field(default_factory=list)
