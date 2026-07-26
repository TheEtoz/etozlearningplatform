"""Student-facing coding path routes."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.dependencies import get_current_user
from backend.models.user import User
from backend.schemas.path import PathModuleResponse
from backend.services.path_service import build_path_for_user

router = APIRouter(prefix="/path", tags=["Coding Path"])


@router.get("", response_model=list[PathModuleResponse])
def read_coding_path(
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> list[dict]:
    """Return the free-jump coding path with completion status."""

    return build_path_for_user(database, current_user.id)
