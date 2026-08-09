"""Legacy coding-path route — path is class-scoped."""

from fastapi import APIRouter, Depends

from backend.dependencies import get_current_user
from backend.models.user import User
from backend.schemas.path import PathModuleResponse

router = APIRouter(prefix="/path", tags=["Coding Path"])


@router.get("", response_model=list[PathModuleResponse])
def read_coding_path(
    _: User = Depends(get_current_user),
) -> list[PathModuleResponse]:
    """Global coding path is disabled — students use class paths."""

    return []
