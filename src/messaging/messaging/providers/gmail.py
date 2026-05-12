import asyncio
import base64
import logging
from email.mime.text import MIMEText

from google.auth.exceptions import RefreshError
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from local_infrastructure.factory.broker_interface import NonRetryableError
from messaging.schemas import EmailProvider

from .base import CreatedDraft, EmailDraftProvider, OAuthCredentials

log = logging.getLogger(__name__)

GMAIL_TOKEN_URI = "https://oauth2.googleapis.com/token"
GMAIL_SCOPES = ("https://www.googleapis.com/auth/gmail.compose",)


class GmailDraftProvider(EmailDraftProvider):
    """Writes drafts to the user's Gmail account via the Drafts API.

    The googleapiclient stack is synchronous; we wrap the blocking call in
    ``asyncio.to_thread`` so the async handler isn't blocked at
    ``RABBIT_PREFETCH=5``. Service is built per-call (cheap with
    ``static_discovery=True`` — no network discovery doc fetch).
    """

    name = EmailProvider.GMAIL

    async def create_draft(
        self,
        *,
        to: str,
        subject: str,
        body: str,
        oauth_credentials: OAuthCredentials,
    ) -> CreatedDraft:
        try:
            draft_id = await asyncio.to_thread(
                _create_draft_blocking,
                to=to, subject=subject, body=body, oauth=oauth_credentials,
            )
        except RefreshError as e:
            # Refresh token is invalid/revoked — re-delivery won't help.
            raise NonRetryableError(f"Gmail OAuth refresh failed: {e}") from e
        except HttpError as e:
            if _is_auth_error(e):
                raise NonRetryableError(f"Gmail auth error: {e}") from e
            raise
        return CreatedDraft(provider=EmailProvider.GMAIL, provider_draft_id=draft_id)


def _create_draft_blocking(*, to: str, subject: str, body: str, oauth: OAuthCredentials) -> str:
    creds = Credentials(
        token=None,
        refresh_token=oauth.refresh_token,
        client_id=oauth.client_id,
        client_secret=oauth.client_secret,
        token_uri=GMAIL_TOKEN_URI,
        scopes=list(GMAIL_SCOPES),
    )
    service = build(
        "gmail",
        "v1",
        credentials=creds,
        cache_discovery=False,
        static_discovery=True,
    )
    raw = _encode_mime(to=to, subject=subject, body=body)
    result = (
        service.users()
        .drafts()
        .create(userId=oauth.user_email, body={"message": {"raw": raw}})
        .execute()
    )
    return str(result["id"])


def _encode_mime(*, to: str, subject: str, body: str) -> str:
    msg = MIMEText(body)
    msg["to"] = to
    msg["subject"] = subject
    return base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")


def _is_auth_error(err: HttpError) -> bool:
    """401 → non-retryable. 403 / 429 / 5xx → bubble (handler retries via re-delivery)."""
    return getattr(err.resp, "status", None) == 401
