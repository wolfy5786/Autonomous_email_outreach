import base64
from email import message_from_bytes
from unittest.mock import MagicMock

import pytest
from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError

import messaging.providers.gmail as gmail_mod
from local_infrastructure.factory.broker_interface import NonRetryableError
from messaging.providers import GmailDraftProvider, OAuthCredentials
from messaging.schemas import EmailProvider


def _creds(user_email: str = "me") -> OAuthCredentials:
    return OAuthCredentials(
        refresh_token="rt", client_id="cid", client_secret="cs", user_email=user_email,
    )


def _http_error(status: int, content: bytes = b"{}") -> HttpError:
    resp = MagicMock(status=status, reason="X")
    return HttpError(resp=resp, content=content)


def _patch_build(mocker, *, draft_id: str = "draft-123", side_effect=None):
    """Patch ``messaging.providers.gmail.build`` to return a chain that yields
    {"id": draft_id} on .execute() (or raises ``side_effect``).

    Returns the underlying drafts mock so tests can inspect ``.create.call_args``.
    """
    create_call = MagicMock()
    if side_effect is not None:
        create_call.execute.side_effect = side_effect
    else:
        create_call.execute.return_value = {"id": draft_id}
    drafts_mock = MagicMock()
    drafts_mock.create.return_value = create_call
    mock_service = MagicMock()
    mock_service.users.return_value.drafts.return_value = drafts_mock
    mocker.patch.object(gmail_mod, "build", return_value=mock_service)
    return drafts_mock


class TestGmailDraftProviderHappyPath:
    async def test_returns_created_draft(self, mocker):
        _patch_build(mocker, draft_id="draft-abc")
        provider = GmailDraftProvider()
        result = await provider.create_draft(
            to="sam@acme.com",
            subject="hi",
            body="hello there",
            oauth_credentials=_creds(),
        )
        assert result.provider is EmailProvider.GMAIL
        assert result.provider_draft_id == "draft-abc"

    async def test_calls_create_with_correct_user_id(self, mocker):
        drafts_mock = _patch_build(mocker)
        provider = GmailDraftProvider()
        await provider.create_draft(
            to="sam@acme.com",
            subject="hi",
            body="hello",
            oauth_credentials=_creds(user_email="alice@x.com"),
        )
        kwargs = drafts_mock.create.call_args.kwargs
        assert kwargs["userId"] == "alice@x.com"

    async def test_encodes_mime_with_subject_to_body(self, mocker):
        drafts_mock = _patch_build(mocker)
        provider = GmailDraftProvider()
        await provider.create_draft(
            to="sam@acme.com",
            subject="Quick chat",
            body="Hi Sam — saw the news.",
            oauth_credentials=_creds(),
        )
        body_arg = drafts_mock.create.call_args.kwargs["body"]
        raw = body_arg["message"]["raw"]
        decoded = base64.urlsafe_b64decode(raw)
        msg = message_from_bytes(decoded)
        assert msg["to"] == "sam@acme.com"
        assert msg["subject"] == "Quick chat"
        # MIMEText base64-encodes non-ASCII bodies (em dash) — decode before asserting.
        decoded_body = msg.get_payload(decode=True).decode("utf-8")
        assert "Hi Sam" in decoded_body


class TestGmailDraftProviderErrors:
    async def test_401_invalid_grant_raises_non_retryable(self, mocker):
        _patch_build(
            mocker, side_effect=_http_error(401, b'{"error":"invalid_grant"}')
        )
        provider = GmailDraftProvider()
        with pytest.raises(NonRetryableError):
            await provider.create_draft(
                to="x@y", subject="s", body="hello there", oauth_credentials=_creds(),
            )

    async def test_503_bubbles_as_http_error(self, mocker):
        _patch_build(mocker, side_effect=_http_error(503))
        provider = GmailDraftProvider()
        with pytest.raises(HttpError):
            await provider.create_draft(
                to="x@y", subject="s", body="hello there", oauth_credentials=_creds(),
            )

    async def test_refresh_error_raises_non_retryable(self, mocker):
        _patch_build(mocker, side_effect=RefreshError("token revoked"))
        provider = GmailDraftProvider()
        with pytest.raises(NonRetryableError):
            await provider.create_draft(
                to="x@y", subject="s", body="hello there", oauth_credentials=_creds(),
            )
