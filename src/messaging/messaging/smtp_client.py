"""SMTP email sender with connection pooling and retry."""
import smtplib
import ssl
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dataclasses import dataclass
from typing import Optional


@dataclass
class SmtpConfig:
    host: str = "smtp.gmail.com"
    port: int = 587
    username: str = ""
    password: str = ""
    use_tls: bool = True
    timeout: int = 30
    max_retries: int = 3


class SmtpClient:
    """Send emails via SMTP with retry and TLS support."""

    def __init__(self, config: SmtpConfig) -> None:
        self._config = config
        self._connection: Optional[smtplib.SMTP] = None

    def connect(self) -> None:
        self._connection = smtplib.SMTP(
            self._config.host,
            self._config.port,
            timeout=self._config.timeout,
        )
        if self._config.use_tls:
            context = ssl.create_default_context()
            self._connection.starttls(context=context)
        self._connection.login(self._config.username, self._config.password)

    def send(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        from_email: Optional[str] = None,
    ) -> bool:
        if self._connection is None:
            self.connect()

        sender = from_email or self._config.username
        msg = MIMEMultipart("alternative")
        msg["From"] = sender
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(html_body, "html"))

        for attempt in range(1, self._config.max_retries + 1):
            try:
                self._connection.sendmail(sender, [to_email], msg.as_string())
                return True
            except smtplib.SMTPException as e:
                if attempt == self._config.max_retries:
                    raise
                wait = 2 ** attempt
                time.sleep(wait)
                self.connect()  # reconnect

        return False

    def disconnect(self) -> None:
        if self._connection:
            try:
                self._connection.quit()
            except smtplib.SMTPException:
                pass
            self._connection = None
