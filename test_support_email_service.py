"""Unit and regression tests for Contact Support Email and Open in Email features."""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock
import smtplib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from fastapi.testclient import TestClient
from app.main import app
from app.services.email_service import email_service, EmailService
from app.config import settings


class TestSupportEmailService(unittest.TestCase):
    """Test suite for Contact Support Email submission and EmailService."""

    def setUp(self):
        self.client = TestClient(app)

    def test_01_support_status_endpoint(self):
        """Verify GET /api/support/status returns support metadata and SMTP readiness."""
        res = self.client.get("/api/support/status")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data.get("support_email"), "dataanalystagent@gmail.com")
        self.assertEqual(data.get("helpline"), "+91 9021964018")
        self.assertIn("smtp_configured", data)
        self.assertIn("message", data)

    def test_02_is_smtp_configured_detection(self):
        """Verify is_smtp_configured accurately detects valid vs empty credentials."""
        with patch.object(settings, "SMTP_HOST", ""), \
             patch.object(settings, "SMTP_USER", ""), \
             patch.object(settings, "SMTP_PASSWORD", ""):
            self.assertFalse(EmailService.is_smtp_configured())

        with patch.object(settings, "SMTP_HOST", "  "), \
             patch.object(settings, "SMTP_USER", "user@example.com"), \
             patch.object(settings, "SMTP_PASSWORD", "secret"):
            self.assertFalse(EmailService.is_smtp_configured())

        with patch.object(settings, "SMTP_HOST", "smtp.gmail.com"), \
             patch.object(settings, "SMTP_USER", "dataanalystagent@gmail.com"), \
             patch.object(settings, "SMTP_PASSWORD", "abcd-efgh-ijkl-mnop"):
            self.assertTrue(EmailService.is_smtp_configured())

    def test_03_contact_submission_validation_errors(self):
        """Verify input validation handles empty/short names, invalid emails, and short messages."""
        # 1. Invalid email
        res = self.client.post("/api/support/contact", json={
            "full_name": "Test User",
            "email": "not-an-email",
            "subject": "Help with analytics",
            "message": "This is a detailed inquiry message."
        })
        self.assertEqual(res.status_code, 422)

        # 2. Too short name (< 2 chars)
        res = self.client.post("/api/support/contact", json={
            "full_name": "T",
            "email": "user@example.com",
            "subject": "Help with analytics",
            "message": "This is a detailed inquiry message."
        })
        self.assertEqual(res.status_code, 422)

        # 3. Too short message (< 10 chars)
        res = self.client.post("/api/support/contact", json={
            "full_name": "Test User",
            "email": "user@example.com",
            "subject": "Help",
            "message": "Hi"
        })
        self.assertEqual(res.status_code, 422)

    def test_04_contact_submission_unconfigured_smtp(self):
        """Verify unconfigured SMTP returns HTTP 503 with actionable guidance."""
        with patch.object(EmailService, "is_smtp_configured", return_value=False):
            res = self.client.post("/api/support/contact", json={
                "full_name": "Jane Analyst",
                "email": "jane@example.com",
                "subject": "Need help with multi-dataset join",
                "message": "I am experiencing an issue joining customer and order datasets."
            })
            self.assertEqual(res.status_code, 503)
            data = res.json()
            self.assertIn("SMTP email service is not configured", data.get("detail", ""))
            self.assertIn("dataanalystagent@gmail.com", data.get("detail", ""))

    def test_05_contact_submission_configured_smtp_success(self):
        """Verify configured SMTP successfully sends email and accepts delivery."""
        mock_server = MagicMock()
        with patch.object(EmailService, "is_smtp_configured", return_value=True), \
             patch.object(EmailService, "_create_smtp_connection", return_value=mock_server):
            res = self.client.post("/api/support/contact", json={
                "full_name": "Alex Smith",
                "email": "alex@example.com",
                "subject": "Feature feedback",
                "message": "The multi-file analysis works very well! Suggesting additional charts."
            })
            self.assertEqual(res.status_code, 200)
            data = res.json()
            self.assertTrue(data.get("success"))
            self.assertIn("Thank you! Your message has been sent", data.get("message", ""))

            # Verify SMTP server interaction
            mock_server.sendmail.assert_called_once()
            args, _ = mock_server.sendmail.call_args
            to_recipients = args[1]
            self.assertIn("dataanalystagent@gmail.com", to_recipients)
            mock_server.quit.assert_called_once()

    def test_06_contact_submission_smtp_auth_error_handling(self):
        """Verify SMTP authentication failure returns HTTP 503 with helpful explanation."""
        mock_server = MagicMock()
        mock_server.login.side_effect = smtplib.SMTPAuthenticationError(535, b"Invalid credentials")

        with patch.object(EmailService, "is_smtp_configured", return_value=True), \
             patch("smtplib.SMTP") as mock_smtp:
            mock_smtp.return_value = mock_server
            res = self.client.post("/api/support/contact", json={
                "full_name": "Alex Smith",
                "email": "alex@example.com",
                "subject": "Inquiry",
                "message": "Testing SMTP auth failure handling in the backend."
            })
            self.assertEqual(res.status_code, 503)
            data = res.json()
            self.assertIn("SMTP authentication failed", data.get("detail", ""))

    def test_07_smtp_ssl_port_465_support(self):
        """Verify port 465 creates SMTP_SSL connection."""
        with patch.object(settings, "SMTP_HOST", "smtp.gmail.com"), \
             patch.object(settings, "SMTP_PORT", 465), \
             patch.object(settings, "SMTP_USER", "dataanalystagent@gmail.com"), \
             patch.object(settings, "SMTP_PASSWORD", "secret"), \
             patch("smtplib.SMTP_SSL") as mock_ssl:
            mock_instance = MagicMock()
            mock_ssl.return_value = mock_instance

            server = EmailService._create_smtp_connection()
            mock_ssl.assert_called_once_with("smtp.gmail.com", 465, timeout=15)
            mock_instance.login.assert_called_once_with("dataanalystagent@gmail.com", "secret")
            self.assertEqual(server, mock_instance)

    def test_08_password_reset_email_remains_functional(self):
        """Verify password reset workflow continues to operate without regression."""
        with patch.object(EmailService, "is_smtp_configured", return_value=False):
            sent, url = EmailService.send_password_reset_email(
                to_email="user@example.com",
                reset_token="sample-token-12345",
                user_name="Test User",
            )
            self.assertFalse(sent)
            self.assertIn("sample-token-12345", url)


if __name__ == "__main__":
    unittest.main()
