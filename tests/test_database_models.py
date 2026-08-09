"""Tests for the Step 2 database foundation."""

from sqlalchemy import UniqueConstraint
from sqlalchemy.orm import configure_mappers

import backend.models  # noqa: F401 -- registers all model tables
from backend.config import Settings
from backend.database import Base


def test_settings_accept_database_url_override() -> None:
    """Settings should support deployment-specific environment values."""
    custom_url = "postgresql+psycopg2://example:secret@db/etoz"

    configured = Settings(database_url=custom_url, _env_file=None)

    assert configured.database_url == custom_url


def test_all_expected_tables_are_registered() -> None:
    """Alembic must be able to discover every database table."""
    configure_mappers()

    assert set(Base.metadata.tables) == {
        "users",
        "auth_email_tokens",
        "quizzes",
        "questions",
        "quiz_attempts",
        "quiz_questions",
        "subjects",
        "topics",
        "question_topics",
        "coding_modules",
        "module_blocks",
        "submissions",
        "progress",
        "classes",
        "class_enrollments",
        "class_quizzes",
        "class_modules",
        "class_announcements",
    }


def test_user_topic_progress_is_unique() -> None:
    """A user should have only one aggregate record per topic."""
    progress_table = Base.metadata.tables["progress"]
    unique_columns = {
        tuple(constraint.columns.keys())
        for constraint in progress_table.constraints
        if isinstance(constraint, UniqueConstraint)
    }

    assert ("user_id", "topic") in unique_columns


def test_submission_foreign_keys_define_safe_delete_behavior() -> None:
    """User cleanup cascades while question history remains protected."""
    submission_table = Base.metadata.tables["submissions"]
    on_delete_by_column = {
        foreign_key.parent.name: foreign_key.ondelete
        for foreign_key in submission_table.foreign_keys
    }

    assert on_delete_by_column == {
        "question_id": "RESTRICT",
        "user_id": "CASCADE",
        "class_id": "SET NULL",
    }
