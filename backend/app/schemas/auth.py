"""Pydantic schemas for Authentication and User management."""

from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


class UserRegisterRequest(BaseModel):
    """Schema for user registration request."""

    full_name: Optional[str] = Field(None, min_length=1, max_length=100, description="User full name")
    username: Optional[str] = Field(None, min_length=2, max_length=50, description="Optional unique username")
    email: EmailStr = Field(..., description="Valid unique email address")
    password: str = Field(..., min_length=8, max_length=128, description="Minimum 8 characters with complexity")
    confirm_password: Optional[str] = Field(None, min_length=8, max_length=128, description="Must match password if provided")

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("username")
    @classmethod
    def sanitize_username(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            cleaned = v.strip()
            return cleaned if cleaned else None
        return None

    @field_validator("full_name")
    @classmethod
    def sanitize_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            cleaned = v.strip()
            return cleaned if cleaned else None
        return None

    @model_validator(mode="after")
    def validate_password_match(self):
        if self.confirm_password is not None and self.password != self.confirm_password:
            raise ValueError("Passwords do not match.")
        return self


class UserLoginRequest(BaseModel):
    """Schema for user login request supporting email, username, or email_or_username."""

    email: Optional[str] = None
    email_or_username: Optional[str] = None
    username: Optional[str] = None
    password: str
    remember_me: Optional[bool] = False

    @model_validator(mode="after")
    def check_identifier_present(self):
        if not self.email and not self.email_or_username and not self.username:
            raise ValueError("Email or username is required.")
        return self


class UserSummary(BaseModel):
    """Public safe user representation - NEVER exposes password or password_hash."""

    id: int
    username: Optional[str] = None
    full_name: Optional[str] = "User"
    email: EmailStr
    role: Optional[str] = "user"

    class Config:
        from_attributes = True


class UserDetailResponse(BaseModel):
    """Detailed user profile for /api/auth/me."""

    id: int
    username: Optional[str] = None
    full_name: Optional[str] = "User"
    email: EmailStr
    role: Optional[str] = "user"
    is_active: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class RegisterResponse(BaseModel):
    """Response returned upon successful user registration."""

    message: str = "User created successfully"
    user: UserSummary


class TokenResponse(BaseModel):
    """JWT Token authentication response upon login."""

    access_token: str
    token_type: str = "bearer"
    user: UserSummary


class TokenPayload(BaseModel):
    """Decoded JWT payload data."""

    sub: Optional[str] = None
    email: Optional[str] = None
    exp: Optional[int] = None
    iat: Optional[int] = None
    type: Optional[str] = None


class SignupRequest(BaseModel):
    """Schema for signup request."""
    username: str
    email: EmailStr
    password: str


class SignupResponse(BaseModel):
    """Schema for signup response."""
    message: str = "User created successfully"
    user: Any


class LoginRequest(BaseModel):
    """Schema for login request with username or email."""
    email_or_username: str
    password: str


class ForgotPasswordRequest(BaseModel):
    """Schema for requesting a password reset email."""
    email: EmailStr = Field(..., description="Registered account email address")

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.strip().lower()


class ForgotPasswordResponse(BaseModel):
    """Generic response for password reset requests to prevent account enumeration."""
    message: str = "If an account with that email exists, password reset instructions have been sent."
    dev_reset_url: Optional[str] = None


class VerifyResetTokenResponse(BaseModel):
    """Response verifying token validity before rendering reset form."""
    valid: bool = True
    message: str = "Token is valid."


class ResetPasswordRequest(BaseModel):
    """Schema for resetting password using a verified single-use token."""
    token: str = Field(..., min_length=10, description="Single-use password reset token")
    new_password: str = Field(..., min_length=8, max_length=128, description="New password meeting complexity requirements")
    confirm_password: Optional[str] = Field(None, min_length=8, max_length=128, description="Password confirmation")

    @model_validator(mode="after")
    def validate_password_match(self):
        if self.confirm_password is not None and self.new_password != self.confirm_password:
            raise ValueError("Passwords do not match.")
        return self


class ResetPasswordResponse(BaseModel):
    """Response confirming successful password reset."""
    message: str = "Password has been reset successfully. You can now log in with your new password."


# Compatibility aliases
UserRegister = UserRegisterRequest
UserLogin = UserLoginRequest
UserResponse = UserDetailResponse
Token = TokenResponse
