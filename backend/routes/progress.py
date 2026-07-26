"""Versioned learning-progress API routes."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.dependencies import get_current_user
from backend.models.user import User
from backend.schemas.progress import ProgressResponse, ProgressSummary
from backend.services.progress_service import (
    get_progress_summary,
    list_user_progress,
)

router = APIRouter(prefix="/progress", tags=["Progress"])


@router.get("", response_model=list[ProgressResponse])
def list_my_progress(
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> list[ProgressResponse]:
    """Return per-topic progress for the authenticated student."""

    rows = list_user_progress(database, user_id=current_user.id)
    return [ProgressResponse.model_validate(row) for row in rows]


@router.get("/summary", response_model=ProgressSummary)
def read_progress_summary(
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> ProgressSummary:
    """Return dashboard totals computed from stored Progress rows."""

    return get_progress_summary(database, user_id=current_user.id)
