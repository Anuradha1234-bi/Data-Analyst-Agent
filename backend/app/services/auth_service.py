from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.logger import logger
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.schemas.auth import LoginRequest, SignupRequest, SignupResponse, TokenResponse
from app.schemas.user import UserResponse


class AuthService:
    """Business service managing user registration, authentication, and user queries."""

    @staticmethod
    def signup(db: Session, data: SignupRequest) -> SignupResponse:
        """
        Register a new regular user.
        Rejects duplicate email or username with 409 Conflict.
        Enforces role = 'user'.
        """
        # Check duplicate email
        existing_email = db.query(User).filter(User.email == data.email.lower()).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this email address already exists.",
            )

        # Check duplicate username
        existing_username = db.query(User).filter(User.username == data.username).first()
        if existing_username:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A user with this username already exists.",
            )

        # Hash password and create user with default role 'user'
        hashed_pw = hash_password(data.password)
        new_user = User(
            username=data.username,
            email=data.email.lower(),
            hashed_password=hashed_pw,
            role="user",
            is_active=True,
        )

        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        logger.info(f"User registered successfully: id={new_user.id}, username='{new_user.username}'")

        return SignupResponse(
            message="User created successfully",
            user=UserResponse.model_validate(new_user),
        )

    @staticmethod
    def login(db: Session, credentials: LoginRequest) -> TokenResponse:
        """
        Authenticate user by username or email.
        Issues JWT access token on success.
        Returns generic 401 error on invalid credentials without leaking account existence.
        """
        identifier = credentials.email_or_username.strip().lower()
        user = (
            db.query(User)
            .filter((User.email == identifier) | (User.username == credentials.email_or_username.strip()))
            .first()
        )

        generic_auth_error = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username/email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

        if not user:
            logger.info(f"Login failed: identifier '{identifier}' not found.")
            raise generic_auth_error

        if not verify_password(credentials.password, user.hashed_password):
            logger.info(f"Login failed: invalid password for user id={user.id}.")
            raise generic_auth_error

        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is inactive. Please contact support.",
            )

        # Generate JWT access token with sub, role, and expiration
        access_token = create_access_token(
            data={
                "sub": str(user.id),
                "role": user.role,
                "username": user.username,
            }
        )

        logger.info(f"User logged in successfully: id={user.id}, username='{user.username}'")
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            user=UserResponse.model_validate(user),
        )

    @staticmethod
    def get_all_users(db: Session) -> List[UserResponse]:
        """Fetch all registered users (admin only query). Excludes sensitive fields."""
        users = db.query(User).order_by(User.id.asc()).all()
        return [UserResponse.model_validate(u) for u in users]

    @staticmethod
    def seed_admin_user(
        db: Session,
        username: str = "admin",
        email: str = "admin@example.com",
        password: str = "AdminPassword123!",
    ) -> User:
        """Seed or ensure presence of an administrative user."""
        existing = db.query(User).filter((User.username == username) | (User.email == email)).first()
        if existing:
            if existing.role != "admin":
                existing.role = "admin"
                db.commit()
                db.refresh(existing)
            return existing

        admin_user = User(
            username=username,
            email=email.lower(),
            hashed_password=hash_password(password),
            role="admin",
            is_active=True,
        )
        db.add(admin_user)
        db.commit()
        db.refresh(admin_user)
        logger.info(f"Admin user seeded successfully: username='{username}'")
        return admin_user
