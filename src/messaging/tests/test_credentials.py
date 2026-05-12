import pytest

from messaging.credentials import CredentialsNotFoundError, CredentialsResolver


class TestCredentialsResolver:
    def test_resolves_with_all_env_vars(self):
        env = {
            "GMAIL_REFRESH_TOKEN_ALICE": "rt-1",
            "GMAIL_USER_EMAIL_ALICE": "alice@example.com",
        }
        resolver = CredentialsResolver(client_id="cid", client_secret="cs", env=env)
        creds = resolver.resolve("alice")
        assert creds.refresh_token == "rt-1"
        assert creds.user_email == "alice@example.com"
        assert creds.client_id == "cid"
        assert creds.client_secret == "cs"

    def test_user_email_defaults_to_me(self):
        env = {"GMAIL_REFRESH_TOKEN_BOB": "rt-2"}
        resolver = CredentialsResolver(client_id="cid", client_secret="cs", env=env)
        creds = resolver.resolve("bob")
        assert creds.user_email == "me"

    def test_uppercases_credentials_ref(self):
        env = {"GMAIL_REFRESH_TOKEN_CAROL": "rt-3"}
        resolver = CredentialsResolver(client_id="cid", client_secret="cs", env=env)
        creds = resolver.resolve("Carol")
        assert creds.refresh_token == "rt-3"

    def test_missing_refresh_token_raises(self):
        resolver = CredentialsResolver(client_id="cid", client_secret="cs", env={})
        with pytest.raises(CredentialsNotFoundError, match="GMAIL_REFRESH_TOKEN_DAVE"):
            resolver.resolve("dave")

    def test_empty_credentials_ref_raises(self):
        resolver = CredentialsResolver(client_id="cid", client_secret="cs", env={})
        with pytest.raises(CredentialsNotFoundError, match="empty"):
            resolver.resolve("")

    def test_constructor_requires_client_id(self):
        with pytest.raises(ValueError, match="client_id"):
            CredentialsResolver(client_id="", client_secret="cs")

    def test_constructor_requires_client_secret(self):
        with pytest.raises(ValueError, match="client_secret"):
            CredentialsResolver(client_id="cid", client_secret="")

    def test_falls_back_to_os_environ(self, monkeypatch):
        monkeypatch.setenv("GMAIL_REFRESH_TOKEN_TEST", "rt-x")
        resolver = CredentialsResolver(client_id="cid", client_secret="cs")
        creds = resolver.resolve("test")
        assert creds.refresh_token == "rt-x"
