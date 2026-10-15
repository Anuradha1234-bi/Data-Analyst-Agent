"""Email delivery service supporting production SMTP and safe local development fallback."""

import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Tuple, Optional
from app.config import settings

logger = logging.getLogger("auth.email")


class EmailService:
    """Service for dispatching transactional authentication emails."""

    @classmethod
    def is_smtp_configured(cls) -> bool:
        """Verify whether SMTP host and credentials are fully specified."""
        return bool(settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD)

    @classmethod
    def send_password_reset_email(
        cls, to_email: str, reset_token: str, user_name: Optional[str] = None
    ) -> Tuple[bool, str]:
        """Dispatch a single-use password reset link via SMTP or log safe development link.

        Returns:
            Tuple[bool, str]: (sent_via_smtp, reset_url)
        """
        display_name = user_name or "Data Analyst"
        reset_url = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"
        expire_minutes = settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES

        subject = f"Reset your password - {settings.PROJECT_NAME}"

        text_content = f"""Hello {display_name},

We received a request to reset your password for {settings.PROJECT_NAME} ({to_email}).

To choose a new password, click the link below (valid for {expire_minutes} minutes):
{reset_url}

If you did not make this request, you can safely ignore this email. Your password will not change.

Best regards,
The {settings.PROJECT_NAME} Team
"""

        html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Reset Your Password</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #F8FAFC; margin: 0; padding: 24px; color: #0F172A;">
  <table width="100%" border="0" cellspacing="0" cellpadding="0" style="max-width: 560px; margin: 0 auto; background-color: #FFFFFF; border-radius: 12px; border: 1px solid #E2E8F0; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);">
    <tr>
      <td style="background-color: #2563EB; padding: 24px 32px; text-align: left;">
        <span style="font-size: 20px; font-weight: 700; color: #FFFFFF; letter-spacing: -0.5px;">{settings.PROJECT_NAME}</span>
      </td>
    </tr>
    <tr>
      <td style="padding: 32px;">
        <h2 style="font-size: 18px; font-weight: 600; margin-top: 0; margin-bottom: 16px; color: #0F172A;">Password Reset Request</h2>
        <p style="font-size: 14px; line-height: 1.6; color: #475569; margin-bottom: 24px;">
          Hello <strong>{display_name}</strong>,<br><br>
          We received a request to reset your password for your account (<strong>{to_email}</strong>). Click the button below to set a new password. This link is valid for <strong>{expire_minutes} minutes</strong> and can only be used once.
        </p>
        <div style="text-align: center; margin: 32px 0;">
          <a href="{reset_url}" style="background-color: #2563EB; color: #FFFFFF; padding: 12px 28px; font-size: 14px; font-weight: 600; text-decoration: none; border-radius: 8px; display: inline-block;">Reset Password</a>
        </div>
        <p style="font-size: 13px; line-height: 1.5; color: #64748B; margin-bottom: 8px;">
          If the button above does not work, copy and paste this URL into your browser:
        </p>
        <p style="font-size: 12px; word-break: break-all; color: #2563EB; background: #F1F5F9; padding: 10px; border-radius: 6px;">
          {reset_url}
        </p>
        <hr style="border: 0; border-top: 1px solid #E2E8F0; margin: 24px 0;">
        <p style="font-size: 12px; color: #94A3B8; margin-bottom: 0;">
          If you did not request a password reset, you can safely ignore this message. Your account remains completely secure.
        </p>
      </td>
    </tr>
  </table>
</body>
</html>
"""

        if cls.is_smtp_configured():
            try:
                msg = MIMEMultipart("alternative")
                msg["Subject"] = subject
                msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
                msg["To"] = to_email

                part1 = MIMEText(text_content, "plain", "utf-8")
                part2 = MIMEText(html_content, "html", "utf-8")
                msg.attach(part1)
                msg.attach(part2)

                server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10)
                if settings.SMTP_TLS:
                    server.starttls()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(settings.SMTP_FROM_EMAIL, [to_email], msg.as_string())
                server.quit()

                logger.info(f"Password reset email dispatched via SMTP to {to_email}")
                return True, reset_url
            except Exception as e:
                logger.error(f"Failed to dispatch password reset email via SMTP to {to_email}: {e}")
                # Fallback to dev log if SMTP connection fails
                return False, reset_url
        else:
            # Safe development workflow
            logger.info(f"[DEV WORKFLOW] SMTP not configured. Password reset link for {to_email}: {reset_url}")
            return False, reset_url


email_service = EmailService()
