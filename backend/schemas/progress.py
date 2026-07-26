"""Response schemas for student learning progress."""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ProgressResponse(BaseModel):
    """Per-topic aggregate performance for one student."""

    model_config = ConfigDict(from_attributes=True)

    topic: str
    questions_attempted: int = Field(ge=0)
    questions_correct: int = Field(ge=0)
    accuracy: Decimal = Field(ge=0, le=100)


class ProgressSummary(BaseModel):
    """High-level totals used by the future dashboard."""

    questions_attempted: int = Field(default=0, ge=0)
    questions_correct: int = Field(default=0, ge=0)
    overall_accuracy: Decimal = Field(
        default=Decimal("0.00"),
        ge=0,
        le=100,
    )
    weak_topics: list[str] = Field(default_factory=list)
