from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional, Literal
from enum import Enum
import re

class RoleEnum(str, Enum):
    client = "client"
    artisan = "artisan"
    admin = "admin"

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=72)
    role: RoleEnum
    full_name: Optional[str] = None
    phone: Optional[str] = None
    username: Optional[str] = None

    @field_validator('role')
    @classmethod
    def validate_role(cls, value):
        if value not in ['client', 'artisan', 'admin']:
            raise ValueError("Role must be 'client', 'artisan', or 'admin'")
        return value

    @field_validator('password')
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

class UserOut(BaseModel):
    id: int
    email: EmailStr
    role: str
    full_name: Optional[str] = None
    phone: Optional[str] = None
    username: Optional[str] = None

    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"