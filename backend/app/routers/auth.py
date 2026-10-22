"""Authentication Router - Register, Login, Me, Logout endpoints."""

import re
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.models.password_reset import PasswordResetToken
from app.schemas.auth import (
    UserRegisterRequest,
    UserLoginRequest,
    RegisterResponse,
    TokenResponse,
    UserDetailResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    VerifyResetTokenResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
)
from app.auth.security import (
    hash_password,
    verify_password,
    validate_password_strength,
    create_access_token,
)
from app.auth.dependencies import get_current_user
from app.services.email_service import email_service
from app.auth.rate_limiter import auth_rate_limiter

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
@router.post("/signup", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
def register(request: Request, user_data: UserRegisterRequest, db: Session = Depends(get_db)):
    """Register a new user account with secure password validation, username resolution, and hashing."""
    normalized_email = user_data.email.strip().lower()

    # Determine whether request is hitting /signup or /register for status code compatibility
    is_signup = request.url.path.rstrip("/").endswith("/signup")
    conflict_status = status.HTTP_409_CONFLICT if is_signup else status.HTTP_400_BAD_REQUEST

    # 1. Prevent duplicate email registration
    existing_user = db.query(User).filter(func.lower(User.email) == normalized_email).first()
    if existing_user:
        raise HTTPException(
            status_code=conflict_status,
            detail="Email is already registered. A user with this email address already exists.",
        )

    # 2. Resolve username (custom or auto-derived from email/full_name)
    if user_data.username and user_data.username.strip():
        target_username = user_data.username.strip()
        existing_username = (
            db.query(User).filter(func.lower(User.username) == target_username.lower()).first()
        )
        if existing_username:
            raise HTTPException(
                status_code=conflict_status,
                detail="Username is already taken. A user with this username already exists.",
            )
    else:
        # Auto-generate unique username based on email prefix
        raw_prefix = normalized_email.split("@")[0] or "user"
        cleaned_prefix = re.sub(r"[^a-zA-Z0-9_-]", "_", raw_prefix)[:40] or "user"
        target_username = cleaned_prefix
        suffix = 1
        while db.query(User).filter(func.lower(User.username) == target_username.lower()).first():
            target_username = f"{cleaned_prefix}_{suffix}"[:50]
            suffix += 1

    # 3. Determine full name
    target_full_name = (user_data.full_name or "").strip() or target_username

    # 4. Validate password strength policy
    is_strong, strength_err = validate_password_strength(user_data.password)
    if not is_strong:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=strength_err,
        )

    # 5. Securely hash password
    hashed_password = hash_password(user_data.password)

    # 6. Create and persist user entity with rollback protection
    try:
        new_user = User(
            username=target_username,
            full_name=target_full_name,
            email=normalized_email,
            password_hash=hashed_password,
            hashed_password=hashed_password,
            role="user",
            is_active=True,
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
    except IntegrityError as exc:
        db.rollback()
        error_msg = str(exc.orig) if hasattr(exc, "orig") else str(exc)
        if "users.email" in error_msg:
            raise HTTPException(
                status_code=conflict_status,
                detail="Email is already registered. A user with this email address already exists.",
            )
        elif "users.username" in error_msg:
            raise HTTPException(
                status_code=conflict_status,
                detail="Username is already taken. A user with this username already exists.",
            )
        else:
            raise HTTPException(
                status_code=conflict_status,
                detail="Database integrity constraint violation during registration.",
            )
    except Exception:
        db.rollback()
        raise

    return {
        "message": "User created successfully" if is_signup else "Registration successful",
        "user": {
            "id": new_user.id,
            "username": new_user.username,
            "full_name": new_user.full_name or new_user.username or "User",
            "email": new_user.email,
            "role": new_user.role or "user",
        },
    }


@router.post("/login", response_model=TokenResponse)
def login(login_data: UserLoginRequest, db: Session = Depends(get_db)):
    """Authenticate user credentials and issue signed JWT token."""
    raw_identifier = login_data.email or login_data.email_or_username or login_data.username or ""
    normalized_identifier = raw_identifier.strip().lower()

    # Generic authentication error to avoid leaking whether identifier or password was incorrect
    error_detail = (
        "Invalid username/email or password"
        if (login_data.email_or_username or login_data.username)
        else "Invalid email or password."
    )
    auth_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=error_detail,
        headers={"WWW-Authenticate": "Bearer"},
    )

    user = (
        db.query(User)
        .filter(
            (func.lower(User.email) == normalized_identifier)
            | (func.lower(User.username) == normalized_identifier)
        )
        .first()
    )
    if not user:
        raise auth_exception

    pwd_hash = user.password_hash or user.hashed_password or getattr(user, "effective_password_hash", "")
    if not verify_password(login_data.password, pwd_hash):
        raise auth_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is deactivated.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Calculate token expiration
    expires_delta = timedelta(days=7) if login_data.remember_me else None
    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email, "username": user.username, "role": user.role},
        expires_delta=expires_delta,
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "full_name": user.full_name or user.username or "User",
            "email": user.email,
            "role": user.role or "user",
        },
    }


@router.get("/me", response_model=UserDetailResponse)
def get_me(current_user: User = Depends(get_current_user)):
    """Get authenticated user profile details. Never returns password hashes."""
    return current_user


@router.post("/logout")
def logout(current_user: User = Depends(get_current_user)):
    """Logout authenticated user session."""
    return {"message": "Successfully logged out."}


@router.post("/forgot-password", response_model=ForgotPasswordResponse)
def forgot_password(
    request: Request,
    payload: ForgotPasswordRequest,
    db: Session = Depends(get_db),
):
    """Initiate a secure password reset workflow.

    Generates a cryptographically strong single-use token, persists only its SHA-256
    digest, and dispatches via SMTP or development fallback. Returns a generic
    message preventing account enumeration.
    """
    client_ip = request.client.host if request.client else "unknown"
    auth_rate_limiter.check_or_raise(f"fp_{client_ip}", max_requests=10, window_seconds=900)

    normalized_email = payload.email.strip().lower()
    user = db.query(User).filter(func.lower(User.email) == normalized_email).first()

    dev_url: Optional[str] = None

    if user and user.is_active:
        # Invalidate previously active unused tokens for this account
        db.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used == False,
        ).update({"used": True})

        # Generate single-use high-entropy token and hash it with SHA-256
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

        expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES
        )

        reset_record = PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
            used=False,
        )
        db.add(reset_record)
        db.commit()

        # Dispatch via email service
        is_sent, reset_url = email_service.send_password_reset_email(
            to_email=user.email,
            reset_token=raw_token,
            user_name=user.full_name or user.username,
        )

        # Expose dev URL only in development environments for local verification
        if settings.APP_ENV != "production":
            dev_url = reset_url

    # Always return a generic confirmation message to eliminate account enumeration risk
    return ForgotPasswordResponse(
        message="If an account with that email exists, password reset instructions have been sent.",
        dev_reset_url=dev_url,
    )


@router.get("/verify-reset-token", response_model=VerifyResetTokenResponse)
def verify_reset_token(token: str, db: Session = Depends(get_db)):
    """Validate that a reset token exists, is unexpired, and has not yet been consumed."""
    if not token or len(token) < 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token.",
        )

    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    now_utc = datetime.now(timezone.utc)

    record = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.token_hash == token_hash, PasswordResetToken.used == False)
        .first()
    )

    if not record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token.",
        )

    record_exp = record.expires_at
    if record_exp.tzinfo is None:
        record_exp = record_exp.replace(tzinfo=timezone.utc)

    if record_exp < now_utc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password reset token has expired. Please request a new one.",
        )

    return VerifyResetTokenResponse(valid=True, message="Token is valid.")


@router.post("/reset-password", response_model=ResetPasswordResponse)
def reset_password(
    request: Request,
    payload: ResetPasswordRequest,
    db: Session = Depends(get_db),
):
    """Apply a new password using a validated single-use reset token."""
    client_ip = request.client.host if request.client else "unknown"
    auth_rate_limiter.check_or_raise(f"rp_{client_ip}", max_requests=10, window_seconds=900)

    # 1. Validate password strength against policy
    is_strong, strength_err = validate_password_strength(payload.new_password)
    if not is_strong:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=strength_err,
        )

    # 2. Verify token
    token_hash = hashlib.sha256(payload.token.encode("utf-8")).hexdigest()
    now_utc = datetime.now(timezone.utc)

    record = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.token_hash == token_hash, PasswordResetToken.used == False)
        .first()
    )

    if not record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset token.",
        )

    record_exp = record.expires_at
    if record_exp.tzinfo is None:
        record_exp = record_exp.replace(tzinfo=timezone.utc)

    if record_exp < now_utc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password reset token has expired. Please request a new one.",
        )

    # 3. Lookup user
    user = db.query(User).filter(User.id == record.user_id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is deactivated or no longer available.",
        )

    # 4. Hash new password with Argon2
    new_hashed = hash_password(payload.new_password)
    user.hashed_password = new_hashed
    user.password_hash = new_hashed
    user.updated_at = now_utc

    # 5. Invalidate current token and any existing unused tokens for this user
    record.used = True
    record.used_at = now_utc

    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.used == False,
    ).update({"used": True})

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update password. Please try again.",
        )

    return ResetPasswordResponse(
        message="Password has been reset successfully. You can now log in with your new password."
    )
