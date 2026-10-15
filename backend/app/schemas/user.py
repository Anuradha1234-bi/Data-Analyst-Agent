"""Pydantic schemas for User Authentication and Account management."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, model_validator


class UserRegister(BaseModel):
    """Schema for user registration request."""

    name: str = Field(..., min_length=2, max_length=100, description="Full name")
    email: EmailStr = Field(..., description="Valid corporate or personal email")
    password: str = Field(..., min_length=6, max_length=128, description="Minimum 6 characters")
    confirm_password: str = Field(..., min_length=6, max_length=128)

    @model_validator(mode="after")
    def passwords_match(self):
        if self.password != self.confirm_password:
            raise ValueError("Password and confirm password must match.")
        return self


class UserLogin(BaseModel):
    """Schema for user login request."""

    email: EmailStr
    password: str
    remember_me: Optional[bool] = False


class UserResponse(BaseModel):
    """Schema for safe public user response - NEVER expose password hashes."""

    id: int
    name: Optional[str] = None
    username: Optional[str] = None
    email: EmailStr
    role: Optional[str] = "user"
    is_active: Optional[bool] = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class Token(BaseModel):
    """JWT Token container."""

    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class TokenPayload(BaseModel):
    """Decoded JWT payload data."""

    sub: Optional[str] = None
    exp: Optional[int] = None
