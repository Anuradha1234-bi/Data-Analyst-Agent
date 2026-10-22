"""Support and contact message router."""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from app.services.email_service import email_service

router = APIRouter(prefix="/support", tags=["Support"])


class ContactMessageRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100, description="Full name of sender")
    email: EmailStr = Field(..., description="Valid sender email address")
    subject: str = Field(..., min_length=3, max_length=150, description="Inquiry subject")
    message: str = Field(..., min_length=10, max_length=3000, description="Detailed message")


class ContactMessageResponse(BaseModel):
    success: bool
    message: str


@router.get("/status")
def get_support_status():
    """Check support email delivery readiness."""
    configured = email_service.is_smtp_configured()
    return {
        "support_email": "dataanalystagent@gmail.com",
        "helpline": "+91 9021964018",
        "smtp_configured": configured,
        "message": (
            "SMTP email service is operational."
            if configured
            else "SMTP email service is not configured on the backend server. Webmail compose fallback is available."
        ),
    }


@router.post("/contact", response_model=ContactMessageResponse)
def submit_contact_message(payload: ContactMessageRequest):
    """Deliver a support or contact message to dataanalystagent@gmail.com.

    Validates required fields and email syntax. If SMTP is configured, dispatches
    via email. If SMTP is unconfigured, honestly returns an actionable status code
    and message.
    """
    clean_name = payload.full_name.strip()
    clean_email = payload.email.strip().lower()
    clean_subject = payload.subject.strip()
    clean_message = payload.message.strip()

    if not clean_name or not clean_subject or not clean_message:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="All fields are required and cannot be empty.",
        )

    sent, outcome_message = email_service.send_support_email(
        full_name=clean_name,
        email=clean_email,
        subject=clean_subject,
        message=clean_message,
    )

    if not sent:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=outcome_message,
        )

    return ContactMessageResponse(
        success=True,
        message="Thank you! Your message has been sent to dataanalystagent@gmail.com. We will respond shortly.",
    )
