"""Unit tests for SMTP client with mocked SMTP server."""
import unittest
from unittest.mock import patch, MagicMock
from src.messaging.messaging.smtp_client import SmtpClient, SmtpConfig


class TestSmtpClient(unittest.TestCase):

    def setUp(self):
        self.config = SmtpConfig(
            host="smtp.test.com",
            port=587,
            username="test@test.com",
            password="secret",
        )
        self.client = SmtpClient(self.config)

    @patch("src.messaging.messaging.smtp_client.smtplib.SMTP")
    def test_send_success(self, mock_smtp_class):
        mock_smtp = MagicMock()
        mock_smtp_class.return_value = mock_smtp

        self.client.connect()
        result = self.client.send(
            to_email="recipient@test.com",
            subject="Test Subject",
            html_body="<p>Hello</p>",
        )

        self.assertTrue(result)
        mock_smtp.sendmail.assert_called_once()

    @patch("src.messaging.messaging.smtp_client.smtplib.SMTP")
    def test_connect_with_tls(self, mock_smtp_class):
        mock_smtp = MagicMock()
        mock_smtp_class.return_value = mock_smtp

        self.client.connect()

        mock_smtp.starttls.assert_called_once()
        mock_smtp.login.assert_called_once_with("test@test.com", "secret")

    def test_disconnect_no_connection(self):
        # Should not raise even without active connection
        self.client.disconnect()


if __name__ == "__main__":
    unittest.main()
