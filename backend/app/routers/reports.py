"""Reports Router."""

from fastapi import APIRouter, Depends
from app.models.user import User
from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/status")
def reports_status(current_user: User = Depends(get_current_user)):
    """Check reports service readiness."""
    return {"status": "ready", "module": "reports"}
