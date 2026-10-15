from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.database.database import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, SignupRequest, SignupResponse, TokenResponse
from app.schemas.user import UserResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/signup",
    response_model=SignupResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new user",
    description="Create a new user account with unique username and email. Assigns 'user' role.",
)
def signup(request: SignupRequest, db: Session = Depends(get_db)) -> SignupResponse:
    """Register a new user account."""
    return AuthService.signup(db, request)


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="User login",
    description="Authenticate with email/username and password to receive a JWT access token.",
)
def login(credentials: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Authenticate and obtain JWT bearer token."""
    return AuthService.login(db, credentials)


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Current authenticated user",
    description="Retrieve the profile of the currently authenticated user from Bearer JWT token.",
)
def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """Return authenticated user profile."""
    return UserResponse.model_validate(current_user)
