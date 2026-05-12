import pytest

from messaging.providers import (
    CreatedDraft,
    EmailDraftProvider,
    OAuthCredentials,
    StubDraftProvider,
    create_provider,
)
from messaging.schemas import EmailProvider


def _creds() -> OAuthCredentials:
    return OAuthCredentials(refresh_token="r", client_id="cid", client_secret="cs")


class TestStubDraftProvider:
    async def test_create_draft_returns_stub_prefixed_id(self):
        provider = StubDraftProvider()
        result = await provider.create_draft(
            to="x@y", subject="hi", body="hello there", oauth_credentials=_creds()
        )
        assert isinstance(result, CreatedDraft)
        assert result.provider is EmailProvider.STUB
        assert result.provider_draft_id.startswith("stub-")

    async def test_two_calls_produce_distinct_ids(self):
        provider = StubDraftProvider()
        a = await provider.create_draft(
            to="x@y", subject="s", body="hello there", oauth_credentials=_creds()
        )
        b = await provider.create_draft(
            to="x@y", subject="s", body="hello there", oauth_credentials=_creds()
        )
        assert a.provider_draft_id != b.provider_draft_id

    def test_implements_provider_interface(self):
        # Strategy-pattern sanity — the factory contract relies on this.
        provider = StubDraftProvider()
        assert isinstance(provider, EmailDraftProvider)
        assert provider.name is EmailProvider.STUB


class TestCreateProvider:
    def test_returns_stub_when_name_is_stub(self):
        provider = create_provider("stub")
        assert isinstance(provider, StubDraftProvider)

    def test_case_and_whitespace_insensitive(self):
        assert isinstance(create_provider("  STUB  "), StubDraftProvider)

    def test_uses_settings_default_when_no_name_given(self, monkeypatch):
        # settings.email_provider defaults to "stub" — verify factory honours it.
        from messaging.config import settings

        monkeypatch.setattr(settings, "email_provider", "stub")
        assert isinstance(create_provider(), StubDraftProvider)

    def test_returns_gmail_when_name_is_gmail(self):
        from messaging.providers import GmailDraftProvider

        provider = create_provider("gmail")
        assert isinstance(provider, GmailDraftProvider)

    def test_unknown_provider_raises_value_error(self):
        with pytest.raises(ValueError, match="Unsupported"):
            create_provider("carrier_pigeon")
