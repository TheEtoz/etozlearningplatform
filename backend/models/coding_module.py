"""Duolingo-style coding path modules and ordered levels."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base

if TYPE_CHECKING:
    from backend.models.question import Question


class CodingModule(Base):
    """A section on the coding learning path."""

    __tablename__ = "coding_modules"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    position: Mapped[int] = mapped_column(Integer, default=0, index=True)
    difficulty_label: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    levels: Mapped[list["ModuleLevel"]] = relationship(
        back_populates="module",
        cascade="all, delete-orphan",
        order_by="ModuleLevel.position",
        passive_deletes=True,
    )


class ModuleLevel(Base):
    """One coding question node inside a module (free-jump path)."""

    __tablename__ = "module_levels"
    __table_args__ = (
        UniqueConstraint(
            "module_id",
            "question_id",
            name="uq_module_levels_module_question",
        ),
        UniqueConstraint(
            "module_id",
            "position",
            name="uq_module_levels_module_position",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    module_id: Mapped[int] = mapped_column(
        ForeignKey("coding_modules.id", ondelete="CASCADE"),
        index=True,
    )
    question_id: Mapped[int] = mapped_column(
        ForeignKey("questions.id", ondelete="CASCADE"),
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, default=0)

    module: Mapped["CodingModule"] = relationship(back_populates="levels")
    question: Mapped["Question"] = relationship(back_populates="module_levels")
