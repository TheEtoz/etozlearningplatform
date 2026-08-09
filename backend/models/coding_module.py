"""Class-owned learning modules with ordered content blocks."""

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base

if TYPE_CHECKING:
    from backend.models.classroom import ClassModule, Classroom
    from backend.models.question import Question


class CodingModule(Base):
    """A topic/module on one class path (contains ordered page markers + blocks)."""

    __tablename__ = "coding_modules"
    __table_args__ = (
        UniqueConstraint(
            "class_id",
            "title",
            name="uq_coding_modules_class_id_title",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int] = mapped_column(
        ForeignKey("classes.id", ondelete="CASCADE"),
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    position: Mapped[int] = mapped_column(Integer, default=0, index=True)
    difficulty_label: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    classroom: Mapped["Classroom"] = relationship(back_populates="modules")
    blocks: Mapped[list["ModuleBlock"]] = relationship(
        back_populates="module",
        cascade="all, delete-orphan",
        order_by="ModuleBlock.position",
        passive_deletes=True,
    )
    class_links: Mapped[list["ClassModule"]] = relationship(
        back_populates="module",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ModuleBlock(Base):
    """One ordered content block inside a module."""

    __tablename__ = "module_blocks"
    __table_args__ = (
        UniqueConstraint(
            "module_id",
            "position",
            name="uq_module_blocks_module_position",
        ),
        CheckConstraint(
            "type IN ('lecture', 'text', 'media', 'mcq', 'coding', 'page')",
            name="valid_module_block_type",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    module_id: Mapped[int] = mapped_column(
        ForeignKey("coding_modules.id", ondelete="CASCADE"),
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, default=0)
    type: Mapped[str] = mapped_column(String(20))
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    question_id: Mapped[int | None] = mapped_column(
        ForeignKey("questions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    module: Mapped["CodingModule"] = relationship(back_populates="blocks")
    question: Mapped["Question | None"] = relationship(back_populates="module_blocks")
