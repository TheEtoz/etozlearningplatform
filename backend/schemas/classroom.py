"""API schemas for school/university classes and enrollment."""

from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import Self

from backend.schemas.quiz import QuizCardResponse


class ClassVisibility(str, Enum):
    """Whether students can browse-enroll without a code."""

    PUBLIC = "public"
    PRIVATE = "private"


class ClassCreate(BaseModel):
    """Teacher input for a new class."""

    title: str = Field(min_length=3, max_length=200)
    description: str = Field(default="", max_length=10_000)
    visibility: ClassVisibility = ClassVisibility.PRIVATE


class ClassUpdate(BaseModel):
    """Partial update for a class."""

    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=10_000)
    visibility: ClassVisibility | None = None
    is_active: bool | None = None


class ClassResponse(BaseModel):
    """Class summary for teachers and enrolled students."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    owner_id: int
    visibility: ClassVisibility
    enrollment_code: str | None = None
    is_active: bool
    created_at: datetime
    quiz_count: int = 0
    module_count: int = 0
    student_count: int = 0
    quiz_ids: list[int] = Field(default_factory=list)
    module_ids: list[int] = Field(default_factory=list)


class ClassPublicCard(BaseModel):
    """Browse card for open (public) classes."""

    id: int
    title: str
    description: str
    owner_username: str
    quiz_count: int = 0
    module_count: int = 0


class ClassEnrollRequest(BaseModel):
    """Join via enrollment code or public class id."""

    code: str | None = Field(default=None, min_length=4, max_length=16)
    class_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def require_one_method(self) -> Self:
        has_code = bool(self.code and self.code.strip())
        has_id = self.class_id is not None
        if has_code == has_id:
            raise ValueError("Provide exactly one of code or class_id")
        if self.code:
            self.code = self.code.strip().upper()
        return self


class ClassPublishQuizzes(BaseModel):
    """Replace published quizzes for a class (order = list order)."""

    quiz_ids: list[int] = Field(default_factory=list)


class ClassPublishModules(BaseModel):
    """Replace published coding modules for a class (order = list order)."""

    module_ids: list[int] = Field(default_factory=list)


class ClassRosterStudent(BaseModel):
    """One enrolled student."""

    user_id: int
    username: str
    email: str
    enrolled_at: datetime


class ClassPerformanceRow(BaseModel):
    """Per-student performance inside one class."""

    user_id: int
    username: str
    quizzes_completed: int
    quizzes_published: int
    average_best_score: Decimal | None = None
    coding_levels_passed: int
    coding_levels_total: int


class ClassQuizCardsResponse(BaseModel):
    """Published quiz cards for an enrolled student."""

    class_id: int
    quizzes: list[QuizCardResponse]


class AnnouncementCreate(BaseModel):
    """Teacher announcement for a class."""

    title: str = Field(min_length=2, max_length=200)
    body: str = Field(min_length=1, max_length=10_000)


class AnnouncementResponse(BaseModel):
    """Announcement shown to teachers and enrolled students."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    class_id: int
    author_id: int
    author_username: str = ""
    title: str
    body: str
    created_at: datetime
