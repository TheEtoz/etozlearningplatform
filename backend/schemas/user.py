"""Pydantic schemas for user authentication requests and responses."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserRole(str, Enum):
    """Supported account roles."""

    STUDENT = "student"
    ADMIN = "admin"


class UserCreate(BaseModel):
    """Data required to register a new account."""

    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class UserLogin(BaseModel):
    """Credentials used to log in."""

    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    """Safe user information returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr
    role: UserRole = UserRole.STUDENT
    email_verified: bool = False
    created_at: datetime


class Token(BaseModel):
    """JWT returned after a successful login."""

    access_token: str
    token_type: str = "bearer"


class MessageResponse(BaseModel):
    """Generic status message."""

    message: str


class EmailRequest(BaseModel):
    """Email-only request for resend / forgot password."""

    email: EmailStr


class TokenRequest(BaseModel):
    """Opaque token from an email link."""

    token: str = Field(min_length=10, max_length=200)


class ResetPasswordRequest(BaseModel):
    """Reset password using an emailed token."""

    token: str = Field(min_length=10, max_length=200)
    new_password: str = Field(min_length=8, max_length=128)
