"""Schemas for the Duolingo-style coding learning path."""

from pydantic import BaseModel, Field


class PathLevelResponse(BaseModel):
    """One coding node on the path."""

    level_id: int
    position: int
    question_id: int
    title: str
    difficulty: str
    topics: list[str] = Field(default_factory=list)
    is_completed: bool = False


class PathModuleResponse(BaseModel):
    """A module containing ordered coding levels."""

    id: int
    title: str
    description: str
    position: int
    difficulty_label: str | None = None
    levels: list[PathLevelResponse] = Field(default_factory=list)
    completed_count: int = 0
    total_count: int = 0


class ModuleCreate(BaseModel):
    """Teacher input for a coding-path module."""

    title: str = Field(min_length=3, max_length=200)
    description: str = Field(default="", max_length=10_000)
    position: int = Field(default=0, ge=0)
    difficulty_label: str | None = Field(default=None, max_length=50)


class ModuleUpdate(BaseModel):
    """Partial module update."""

    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=10_000)
    position: int | None = Field(default=None, ge=0)
    difficulty_label: str | None = Field(default=None, max_length=50)


class ModuleLevelsUpdate(BaseModel):
    """Replace ordered coding question ids for a module."""

    question_ids: list[int] = Field(default_factory=list)


class ModuleAdminResponse(BaseModel):
    """Teacher view of a module."""

    id: int
    title: str
    description: str
    position: int
    difficulty_label: str | None
    question_ids: list[int] = Field(default_factory=list)
