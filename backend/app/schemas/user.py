from __future__ import annotations

import re
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class RoleEnum(StrEnum):
    client = "client"
    artisan = "artisan"
    admin = "admin"


class PublicRoleEnum(StrEnum):
    client = "client"
    artisan = "artisan"


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=72)
    role: PublicRoleEnum
    full_name: str | None = None
    phone: str | None = None
    username: str | None = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, value):
        if value not in {PublicRoleEnum.client, PublicRoleEnum.artisan}:
            raise ValueError("Role must be 'client' or 'artisan'")
        return value

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value):
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters long")

        if not re.search(r"[A-Z]", value):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", value):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"[0-9]", value):
            raise ValueError("Password must contain at least one digit")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", value):
            raise ValueError("Password must contain at least one special character")

        return value


class RegisterResponse(BaseModel):
    id: int
    role: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class UserUpdate(BaseModel):
    full_name: str | None = Field(None, max_length=200)
    phone: str | None = Field(None, max_length=20)
    username: str | None = Field(None, max_length=100)
    avatar: str | None = Field(None, max_length=500)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    role: str
    full_name: str | None = None
    phone: str | None = None
    username: str | None = None
    avatar: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
