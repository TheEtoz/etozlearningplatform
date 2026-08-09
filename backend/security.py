"""Password hashing and JWT token utilities.

Student passwords must never be stored in plain text. JWT tokens let the
frontend prove identity on later requests without sending the password again.
"""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import bcrypt
from jose import JWTError, jwt

from backend.config import settings

ALGORITHM = "HS256"


def generate_url_token(nbytes: int = 32) -> str:
    """Return a URL-safe random token for email links."""

    return secrets.token_urlsafe(nbytes)


def hash_url_token(raw_token: str) -> str:
    """Hash an email token for storage (SHA-256 hex)."""

    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def hash_password(plain_password: str) -> str:
    """Convert a plain-text password into a one-way bcrypt hash."""

    password_bytes = plain_password.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return True when the plain password matches the stored hash."""

    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8"),
    )


def create_access_token(user_id: int) -> str:
    """Create a signed JWT that identifies the user until it expires."""

    expire_at = datetime.now(UTC) + timedelta(
        minutes=settings.access_token_expire_minutes,
    )
    payload = {"sub": str(user_id), "exp": expire_at}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> int | None:
    """Return the user id from a valid token, or None if invalid/expired."""

    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        subject = payload.get("sub")
        if subject is None:
            return None
        return int(subject)
    except (JWTError, ValueError):
        return None
