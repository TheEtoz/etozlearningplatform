"""Email verification and password-reset token workflows."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.config import settings
from backend.models.auth_token import AuthEmailToken
from backend.models.user import User
from backend.security import generate_url_token, hash_password, hash_url_token
from backend.services.email_service import (
    EmailServiceError,
    send_password_reset_email,
    send_verification_email,
)

GENERIC_OK = (
    "If an account exists for that email, we sent instructions. "
    "Check your inbox (and spam)."
)


class AuthEmailError(Exception):
    """Domain error for verify/reset flows."""


def _frontend_link(page: str, token: str) -> str:
    base = settings.frontend_public_url.rstrip("/")
    query = urlencode({"token": token})
    return f"{base}/{page}?{query}"


def issue_email_token(
    database: Session,
    *,
    user: User,
    purpose: str,
    expire_hours: int,
) -> str:
    """Create a single-use token row and return the raw token."""

    raw = generate_url_token()
    row = AuthEmailToken(
        user_id=user.id,
        purpose=purpose,
        token_hash=hash_url_token(raw),
        expires_at=datetime.now(UTC) + timedelta(hours=expire_hours),
    )
    database.add(row)
    database.commit()
    return raw


def _consume_token(
    database: Session,
    *,
    raw_token: str,
    purpose: str,
) -> AuthEmailToken:
    token_hash = hash_url_token(raw_token.strip())
    row = database.scalars(
        select(AuthEmailToken).where(
            AuthEmailToken.token_hash == token_hash,
            AuthEmailToken.purpose == purpose,
        )
    ).first()
    if row is None:
        raise AuthEmailError("Invalid or expired link")
    if row.used_at is not None:
        raise AuthEmailError("This link was already used")
    expires = row.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    if expires < datetime.now(UTC):
        raise AuthEmailError("Invalid or expired link")
    row.used_at = datetime.now(UTC)
    database.commit()
    database.refresh(row)
    return row


def send_verify_for_user(database: Session, user: User) -> None:
    raw = issue_email_token(
        database,
        user=user,
        purpose="verify",
        expire_hours=settings.email_verify_expire_hours,
    )
    link = _frontend_link("VerifyEmail", raw)
    try:
        send_verification_email(
            to_email=user.email,
            username=user.username,
            link=link,
        )
    except EmailServiceError as error:
        raise AuthEmailError(str(error)) from error


def verify_email_token(database: Session, *, raw_token: str) -> User:
    row = _consume_token(database, raw_token=raw_token, purpose="verify")
    user = database.get(User, row.user_id)
    if user is None:
        raise AuthEmailError("Invalid or expired link")
    user.email_verified = True
    user.email_verified_at = datetime.now(UTC)
    database.commit()
    database.refresh(user)
    return user


def resend_verification(database: Session, *, email: str) -> str:
    user = database.scalars(
        select(User).where(User.email == email.strip().lower())
    ).first()
    # Case: emails may be stored mixed-case from older data — also try exact.
    if user is None:
        user = database.scalars(select(User).where(User.email == email.strip())).first()
    if user is not None and not user.email_verified:
        try:
            send_verify_for_user(database, user)
        except AuthEmailError:
            # Still return generic message to avoid leaking config details broadly.
            if settings.debug:
                raise
    return GENERIC_OK


def forgot_password(database: Session, *, email: str) -> str:
    user = database.scalars(
        select(User).where(User.email == email.strip().lower())
    ).first()
    if user is None:
        user = database.scalars(select(User).where(User.email == email.strip())).first()
    if user is not None:
        raw = issue_email_token(
            database,
            user=user,
            purpose="reset",
            expire_hours=settings.email_reset_expire_hours,
        )
        link = _frontend_link("ResetPassword", raw)
        try:
            send_password_reset_email(
                to_email=user.email,
                username=user.username,
                link=link,
            )
        except EmailServiceError as error:
            if settings.debug:
                raise AuthEmailError(str(error)) from error
    return GENERIC_OK


def reset_password(
    database: Session,
    *,
    raw_token: str,
    new_password: str,
) -> User:
    row = _consume_token(database, raw_token=raw_token, purpose="reset")
    user = database.get(User, row.user_id)
    if user is None:
        raise AuthEmailError("Invalid or expired link")
    user.hashed_password = hash_password(new_password)
    # Resetting via email also proves mailbox access.
    if not user.email_verified:
        user.email_verified = True
        user.email_verified_at = datetime.now(UTC)
    database.commit()
    database.refresh(user)
    return user
