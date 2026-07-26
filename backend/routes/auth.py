"""Authentication routes: register, login, and current-user profile."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import get_db
from backend.dependencies import get_current_user
from backend.models.user import User
from backend.schemas.user import Token, UserCreate, UserLogin, UserResponse
from backend.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _is_bootstrap_admin(username: str) -> bool:
    """Return True when this username is listed in ADMIN_USERNAMES."""

    allowed = {name.strip().lower() for name in settings.admin_usernames if name.strip()}
    return username.strip().lower() in allowed


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_user(
    payload: UserCreate,
    database: Session = Depends(get_db),
) -> User:
    """Create a new user account with a hashed password."""

    existing_user = database.query(User).filter(
        or_(User.username == payload.username, User.email == payload.email),
    ).first()
    if existing_user:
        if existing_user.username == payload.username:
            detail = "Username already registered"
        else:
            detail = "Email already registered"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        )

    role = "admin" if _is_bootstrap_admin(payload.username) else "student"
    user = User(
        username=payload.username,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role=role,
    )

    database.add(user)
    try:
        database.commit()
    except IntegrityError as error:
        database.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username or email already registered",
        ) from error

    database.refresh(user)
    return user


@router.post("/login", response_model=Token)
def login_user(
    payload: UserLogin,
    database: Session = Depends(get_db),
) -> Token:
    """Verify credentials and return a JWT access token."""

    user = database.query(User).filter(User.username == payload.username).first()
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return Token(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserResponse)
def read_current_user(current_user: User = Depends(get_current_user)) -> User:
    """Return the profile of the currently authenticated user."""

    return current_user
