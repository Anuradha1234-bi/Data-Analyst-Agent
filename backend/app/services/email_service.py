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
        return bool(
            settings.SMTP_HOST
            and str(settings.SMTP_HOST).strip()
            and settings.SMTP_USER
            and str(settings.SMTP_USER).strip()
            and settings.SMTP_PASSWORD
            and str(settings.SMTP_PASSWORD).strip()
        )

    @classmethod
    def _create_smtp_connection(cls) -> smtplib.SMTP:
        """Create and connect an SMTP or SMTP_SSL client based on configuration."""
        import socket
        port = int(settings.SMTP_PORT or 587)
        host = str(settings.SMTP_HOST).strip()
        timeout = 15

        if port == 465:
            server = smtplib.SMTP_SSL(host, port, timeout=timeout)
        else:
            server = smtplib.SMTP(host, port, timeout=timeout)
            if settings.SMTP_TLS:
                server.starttls()

        server.login(str(settings.SMTP_USER).strip(), str(settings.SMTP_PASSWORD).strip())
        return server

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
                from_email = (
                    settings.SMTP_FROM_EMAIL
                    if settings.SMTP_FROM_EMAIL and "@" in settings.SMTP_FROM_EMAIL and settings.SMTP_FROM_EMAIL != "noreply@datanalyst.ai"
                    else (settings.SMTP_USER or settings.SMTP_FROM_EMAIL)
                )

                msg = MIMEMultipart("alternative")
                msg["Subject"] = subject
                msg["From"] = f"{settings.SMTP_FROM_NAME} <{from_email}>"
                msg["To"] = to_email

                part1 = MIMEText(text_content, "plain", "utf-8")
                part2 = MIMEText(html_content, "html", "utf-8")
                msg.attach(part1)
                msg.attach(part2)

                server = cls._create_smtp_connection()
                server.sendmail(from_email, [to_email], msg.as_string())
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

    @classmethod
    def send_support_email(
        cls, full_name: str, email: str, subject: str, message: str
    ) -> Tuple[bool, str]:
        """Dispatch a user support/contact inquiry to dataanalystagent@gmail.com.

        Returns:
            Tuple[bool, str]: (sent_via_smtp, message_or_error)
        """
        support_destination = "dataanalystagent@gmail.com"
        email_subject = f"[Help & Support] {subject} - from {full_name}"

        body_text = f"""Help & Support Inquiry:
From: {full_name} <{email}>
Subject: {subject}

Message:
{message}
"""

        body_html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Help & Support Message</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #F8FAFC; margin: 0; padding: 24px; color: #0F172A;">
  <table width="100%" border="0" cellspacing="0" cellpadding="0" style="max-width: 580px; margin: 0 auto; background-color: #FFFFFF; border-radius: 12px; border: 1px solid #E2E8F0; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);">
    <tr>
      <td style="background-color: #0B132B; padding: 20px 24px;">
        <span style="font-size: 18px; font-weight: 700; color: #FFFFFF;">AI Data Analyst Agent</span>
        <span style="font-size: 12px; color: #94A3B8; display: block; margin-top: 4px;">Help &amp; Support Inquiry</span>
      </td>
    </tr>
    <tr>
      <td style="padding: 24px;">
        <p style="font-size: 14px; margin-top: 0; color: #334155;"><strong>From:</strong> {full_name} (&lt;<a href="mailto:{email}" style="color: #2563EB;">{email}</a>&gt;)</p>
        <p style="font-size: 14px; color: #334155;"><strong>Subject:</strong> {subject}</p>
        <hr style="border: 0; border-top: 1px solid #E2E8F0; margin: 16px 0;" />
        <p style="font-size: 13px; font-weight: 600; color: #475569; margin-bottom: 8px;">Message:</p>
        <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 14px; font-size: 13px; line-height: 1.6; color: #0F172A; white-space: pre-wrap;">{message}</div>
        <hr style="border: 0; border-top: 1px solid #E2E8F0; margin: 20px 0;" />
        <p style="font-size: 11px; color: #94A3B8; margin-bottom: 0;">Dispatched via AI Data Analyst Agent Help &amp; Support System.</p>
      </td>
    </tr>
  </table>
</body>
</html>
"""

        if cls.is_smtp_configured():
            try:
                from_email = (
                    settings.SMTP_FROM_EMAIL
                    if settings.SMTP_FROM_EMAIL and "@" in settings.SMTP_FROM_EMAIL and settings.SMTP_FROM_EMAIL != "noreply@datanalyst.ai"
                    else (settings.SMTP_USER or settings.SMTP_FROM_EMAIL)
                )

                msg = MIMEMultipart("alternative")
                msg["Subject"] = email_subject
                msg["From"] = f"{settings.SMTP_FROM_NAME} <{from_email}>"
                msg["To"] = support_destination
                msg["Reply-To"] = email

                part1 = MIMEText(body_text, "plain", "utf-8")
                part2 = MIMEText(body_html, "html", "utf-8")
                msg.attach(part1)
                msg.attach(part2)

                server = cls._create_smtp_connection()
                server.sendmail(from_email, [support_destination], msg.as_string())
                server.quit()

                logger.info(f"Support email dispatched via SMTP to {support_destination}")
                return True, "Message delivered successfully to support team."
            except smtplib.SMTPAuthenticationError as auth_err:
                logger.error(f"Failed to authenticate with SMTP server for support inquiry: {auth_err}")
                return False, "SMTP authentication failed: Please check SMTP username and password in backend configuration."
            except (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected) as conn_err:
                logger.error(f"Failed to connect to SMTP server ({settings.SMTP_HOST}:{settings.SMTP_PORT}): {conn_err}")
                return False, f"SMTP server connection failed: Could not connect to {settings.SMTP_HOST}:{settings.SMTP_PORT}."
            except TimeoutError as timeout_err:
                logger.error(f"Timeout connecting to SMTP server ({settings.SMTP_HOST}:{settings.SMTP_PORT}): {timeout_err}")
                return False, f"SMTP server connection timed out while reaching {settings.SMTP_HOST}:{settings.SMTP_PORT}."
            except Exception as e:
                logger.error(f"Failed to dispatch support email via SMTP to {support_destination}: {e}")
                return False, f"SMTP delivery failed: {str(e)}"
        else:
            logger.info(f"[DEV WORKFLOW] SMTP not configured. Support message logged from {email}: {subject}")
            return False, "SMTP email service is not configured on the backend server. Please contact dataanalystagent@gmail.com directly from your email client."


email_service = EmailService()

