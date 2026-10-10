"""Email transport tests: no database, credentials or real network calls."""

import io
import json
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

from flask import Flask

from app.services.email_service import _NoRedirect, send_password_reset_email


class EmailServiceTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            MAIL_PROVIDER="brevo",
            BREVO_API_KEY="test-key-not-real",
            BREVO_SENDER_EMAIL="shop@example.test",
            BREVO_SENDER_NAME="Lego Flower",
        )
        context = self.app.app_context()
        context.push()
        self.addCleanup(context.pop)
        self.opener_patch = patch("app.services.email_service.build_opener")
        self.opener = self.opener_patch.start().return_value
        self.addCleanup(self.opener_patch.stop)
        self.smtp_patch = patch("app.services.email_service.smtplib.SMTP")
        self.smtp = self.smtp_patch.start()
        self.addCleanup(self.smtp_patch.stop)
        self.response = self.opener.open.return_value.__enter__.return_value
        self.response.status = 201
        self.response.read.return_value = b'{"messageId":"test-id"}'

    def send(self, recipient="customer@example.test"):
        return send_password_reset_email(recipient, "https://shop.example/reset/token", "123456")

    def test_https_payload_uses_each_customer_not_sender(self):
        for recipient in ("first@example.test", "second@example.test"):
            self.assertEqual(self.send(recipient), (True, "accepted"))
            request = self.opener.open.call_args.args[0]
            self.assertEqual(request.full_url, "https://api.brevo.com/v3/smtp/email")
            self.assertEqual(request.get_method(), "POST")
            self.assertEqual(request.get_header("Api-key"), "test-key-not-real")
            self.assertEqual(self.opener.open.call_args.kwargs["timeout"], 10)
            payload = json.loads(request.data)
            self.assertEqual(payload["to"], [{"email": recipient}])
            self.assertEqual(payload["sender"]["email"], "shop@example.test")
            self.assertIn("123456", payload["htmlContent"])
            self.assertIn("https://shop.example/reset/token", payload["htmlContent"])
        self.smtp.assert_not_called()

    def test_missing_configuration_fails_without_network(self):
        for key in ("BREVO_API_KEY", "BREVO_SENDER_EMAIL"):
            with patch.dict(self.app.config, {key: ""}):
                self.assertFalse(self.send()[0])
        self.opener.open.assert_not_called()
        self.smtp.assert_not_called()

    def test_http_errors_do_not_leak_response_or_retry(self):
        for status in (400, 401, 402, 403, 429, 500, 302):
            self.opener.open.reset_mock()
            self.opener.open.side_effect = HTTPError(
                "https://api.brevo.com/v3/smtp/email",
                status,
                "error",
                {},
                io.BytesIO(b"SECRET-KEY-AND-RESET-TOKEN"),
            )
            success, error = self.send()
            self.assertFalse(success)
            self.assertIn(str(status), error)
            self.assertNotIn("SECRET", error)
            self.opener.open.assert_called_once()
        self.smtp.assert_not_called()

    def test_network_errors_do_not_retry_or_fallback(self):
        for error in (URLError("private-detail"), TimeoutError("private-detail")):
            self.opener.open.reset_mock()
            self.opener.open.side_effect = error
            success, message = self.send()
            self.assertFalse(success)
            self.assertNotIn("private-detail", message)
            self.opener.open.assert_called_once()
        self.smtp.assert_not_called()

    def test_requires_valid_acceptance_response(self):
        for body in (b"not-json", b"{}", b"[]", b'{"messageId":""}'):
            self.response.read.return_value = body
            self.assertFalse(self.send()[0])
        self.response.status = 200
        self.response.read.return_value = b'{"messageId":"test-id"}'
        self.assertFalse(self.send()[0])

    def test_redirect_is_refused(self):
        self.assertIsNone(
            _NoRedirect().redirect_request(MagicMock(), None, 302, "", {}, "https://other.test")
        )

    def test_unknown_provider_is_rejected(self):
        self.app.config["MAIL_PROVIDER"] = "typo"
        self.assertFalse(self.send()[0])
        self.smtp.assert_not_called()
        self.opener.open.assert_not_called()

    def test_smtp_compatibility(self):
        self.app.config.update(
            MAIL_PROVIDER="smtp",
            MAIL_USERNAME="shop@example.test",
            MAIL_PASSWORD="test-only",
            MAIL_SERVER="smtp.example.test",
            MAIL_PORT=587,
            MAIL_USE_TLS=True,
        )
        self.assertEqual(self.send(), (True, "sent"))
        server = self.smtp.return_value.__enter__.return_value
        server.starttls.assert_called_once()
        self.assertEqual(server.sendmail.call_args.args[1], ["customer@example.test"])
        self.opener.open.assert_not_called()


if __name__ == "__main__":
    unittest.main()
