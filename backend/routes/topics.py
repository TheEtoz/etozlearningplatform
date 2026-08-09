"""Canonical subject areas for filters and teacher multi-select."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.dependencies import get_current_user
from backend.models.user import User
from backend.schemas.question import TopicResponse
from backend.services.topic_service import list_topics

router = APIRouter(prefix="/topics", tags=["Topics"])


@router.get("", response_model=list[TopicResponse])
def read_topics(
    subject: str | None = None,
    _: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> list[TopicResponse]:
    return [
        TopicResponse(
            id=item.id,
            name=item.name,
            subject_id=item.subject_id,
            subject=item.subject.name if item.subject else None,
        )
        for item in list_topics(database, subject=subject)
    ]
