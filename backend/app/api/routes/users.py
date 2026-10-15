from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.dependencies import require_role
from app.database.database import get_db
from app.models.user import User
from app.schemas.user import UserResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/users", tags=["Users Administration"])


@router.get(
    "",
    response_model=List[UserResponse],
    status_code=status.HTTP_200_OK,
    summary="List all registered users (Admin only)",
    description="Retrieve all user records in the system. Requires administrative role.",
)
def list_users(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_role("admin")),
) -> List[UserResponse]:
    """Admin-only endpoint returning all registered users without credentials."""
    return AuthService.get_all_users(db)
