"""Schemas for class learning-path modules and content blocks."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class PathBlockResponse(BaseModel):
    """One student-facing content block inside a module."""

    id: int
    position: int
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    question_id: int | None = None
    title: str | None = None
    description: str = ""
    difficulty: str | None = None
    topics: list[str] = Field(default_factory=list)
    choices: list[str] | None = None
    starter_code: str = ""
    is_completed: bool = False


class PathModuleResponse(BaseModel):
    """A module containing ordered content blocks."""

    id: int
    title: str
    description: str
    position: int
    difficulty_label: str | None = None
    blocks: list[PathBlockResponse] = Field(default_factory=list)
    levels: list[PathBlockResponse] = Field(
        default_factory=list,
        description="Legacy alias: coding blocks only",
    )
    completed_count: int = 0
    total_count: int = 0


class ModuleCreate(BaseModel):
    """Teacher input for a coding-path module (must belong to a class)."""

    class_id: int = Field(ge=1)
    title: str = Field(min_length=3, max_length=200)
    description: str = Field(default="", max_length=50_000)
    position: int = Field(default=0, ge=0)
    difficulty_label: str | None = Field(default=None, max_length=50)


class ModuleUpdate(BaseModel):
    """Partial module update."""

    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=50_000)
    position: int | None = Field(default=None, ge=0)
    difficulty_label: str | None = Field(default=None, max_length=50)


class ModuleBlockCreate(BaseModel):
    """Add or replace a block definition."""

    type: Literal["lecture", "text", "media", "mcq", "coding", "page"]
    payload: dict[str, Any] = Field(default_factory=dict)
    question_id: int | None = None


class ModuleBlocksUpdate(BaseModel):
    """Replace ordered blocks for a module."""

    blocks: list[ModuleBlockCreate] = Field(default_factory=list)


class ModuleLevelsUpdate(BaseModel):
    """Legacy: replace coding question ids (converted to coding blocks)."""

    question_ids: list[int] = Field(default_factory=list)


class ModuleBlockAdminResponse(BaseModel):
    id: int
    position: int
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    question_id: int | None = None


class ModuleAdminResponse(BaseModel):
    """Teacher view of a module."""

    id: int
    class_id: int
    title: str
    description: str
    position: int
    difficulty_label: str | None
    question_ids: list[int] = Field(default_factory=list)
    blocks: list[ModuleBlockAdminResponse] = Field(default_factory=list)
