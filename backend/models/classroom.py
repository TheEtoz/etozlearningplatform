"""School/university class sections with enrollment and published content."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
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
    from backend.models.coding_module import CodingModule
    from backend.models.quiz import Quiz
    from backend.models.quiz_attempt import QuizAttempt
    from backend.models.submission import Submission
    from backend.models.user import User


class Classroom(Base):
    """A teacher-owned class/subject students enroll into."""

    __tablename__ = "classes"
    __table_args__ = (
        CheckConstraint(
            "visibility IN ('public', 'private')",
            name="valid_class_visibility",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    visibility: Mapped[str] = mapped_column(
        String(20),
        default="private",
        server_default="private",
        index=True,
    )
    enrollment_code: Mapped[str] = mapped_column(
        String(16),
        unique=True,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    owner: Mapped["User"] = relationship(back_populates="owned_classes")
    enrollments: Mapped[list["ClassEnrollment"]] = relationship(
        back_populates="classroom",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    class_quizzes: Mapped[list["ClassQuiz"]] = relationship(
        back_populates="classroom",
        cascade="all, delete-orphan",
        order_by="ClassQuiz.position",
        passive_deletes=True,
    )
    class_modules: Mapped[list["ClassModule"]] = relationship(
        back_populates="classroom",
        cascade="all, delete-orphan",
        order_by="ClassModule.position",
        passive_deletes=True,
    )
    modules: Mapped[list["CodingModule"]] = relationship(
        back_populates="classroom",
        cascade="all, delete-orphan",
        order_by="CodingModule.position",
        passive_deletes=True,
    )
    quiz_attempts: Mapped[list["QuizAttempt"]] = relationship(
        back_populates="classroom",
    )
    submissions: Mapped[list["Submission"]] = relationship(
        back_populates="classroom",
    )
    announcements: Mapped[list["ClassAnnouncement"]] = relationship(
        back_populates="classroom",
        cascade="all, delete-orphan",
        order_by="ClassAnnouncement.created_at.desc()",
        passive_deletes=True,
    )


class ClassEnrollment(Base):
    """A student membership in a class."""

    __tablename__ = "class_enrollments"
    __table_args__ = (
        UniqueConstraint(
            "class_id",
            "user_id",
            name="uq_class_enrollments_class_user",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int] = mapped_column(
        ForeignKey("classes.id", ondelete="CASCADE"),
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    enrolled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    classroom: Mapped["Classroom"] = relationship(back_populates="enrollments")
    user: Mapped["User"] = relationship(back_populates="class_enrollments")


class ClassQuiz(Base):
    """A quiz published into a class for enrolled students."""

    __tablename__ = "class_quizzes"
    __table_args__ = (
        UniqueConstraint(
            "class_id",
            "quiz_id",
            name="uq_class_quizzes_class_quiz",
        ),
        UniqueConstraint(
            "class_id",
            "position",
            name="uq_class_quizzes_class_position",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int] = mapped_column(
        ForeignKey("classes.id", ondelete="CASCADE"),
        index=True,
    )
    quiz_id: Mapped[int] = mapped_column(
        ForeignKey("quizzes.id", ondelete="CASCADE"),
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, default=0)
    is_published: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
    )
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    classroom: Mapped["Classroom"] = relationship(back_populates="class_quizzes")
    quiz: Mapped["Quiz"] = relationship(back_populates="class_links")


class ClassModule(Base):
    """A coding-path module published into a class."""

    __tablename__ = "class_modules"
    __table_args__ = (
        UniqueConstraint(
            "class_id",
            "module_id",
            name="uq_class_modules_class_module",
        ),
        UniqueConstraint(
            "class_id",
            "position",
            name="uq_class_modules_class_position",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int] = mapped_column(
        ForeignKey("classes.id", ondelete="CASCADE"),
        index=True,
    )
    module_id: Mapped[int] = mapped_column(
        ForeignKey("coding_modules.id", ondelete="CASCADE"),
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, default=0)
    is_published: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
    )
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    classroom: Mapped["Classroom"] = relationship(back_populates="class_modules")
    module: Mapped["CodingModule"] = relationship(back_populates="class_links")


class ClassAnnouncement(Base):
    """A short notice posted by the class teacher for enrolled students."""

    __tablename__ = "class_announcements"

    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int] = mapped_column(
        ForeignKey("classes.id", ondelete="CASCADE"),
        index=True,
    )
    author_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
    )

    classroom: Mapped["Classroom"] = relationship(back_populates="announcements")
    author: Mapped["User"] = relationship()
