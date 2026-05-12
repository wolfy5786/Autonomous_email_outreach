import os
from collections.abc import Mapping
from typing import Protocol

from messaging.providers.base import OAuthCredentials


class CredentialsNotFoundError(Exception):
    """Raised when OAuth credentials for a campaign cannot be resolved.

    Handler converts this to ``NonRetryableError`` so the message goes to DLQ —
    re-delivery won't help.
    """


class CredentialsResolver:
    """Resolves OAuth credentials for a campaign's email account.

    v1 implementation reads from environment variables. Per-campaign refresh
    tokens are looked up by ``credentials_ref`` (a string the Orchestrator/Web
    UI supplies on campaign create):

        GMAIL_REFRESH_TOKEN_<REF>     - required
        GMAIL_USER_EMAIL_<REF>        - optional, defaults to "me"
        GMAIL_CLIENT_ID               - global, set on the resolver
        GMAIL_CLIENT_SECRET           - global, set on the resolver

    Production swap path: replace this class with a Secrets-Manager-backed one;
    same ``resolve()`` signature.
    """

    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        env: Mapping[str, str] | None = None,
    ) -> None:
        if not client_id:
            raise ValueError("client_id is required (set GMAIL_CLIENT_ID)")
        if not client_secret:
            raise ValueError("client_secret is required (set GMAIL_CLIENT_SECRET)")
        self._client_id = client_id
        self._client_secret = client_secret
        self._env = env if env is not None else os.environ

    def resolve(self, credentials_ref: str) -> OAuthCredentials:
        ref = (credentials_ref or "").strip()
        if not ref:
            raise CredentialsNotFoundError("credentials_ref is empty")
        key = ref.upper()
        refresh_token = self._env.get(f"GMAIL_REFRESH_TOKEN_{key}", "").strip()
        if not refresh_token:
            raise CredentialsNotFoundError(
                f"GMAIL_REFRESH_TOKEN_{key} not set (required for credentials_ref={ref!r})"
            )
        user_email = self._env.get(f"GMAIL_USER_EMAIL_{key}", "").strip() or "me"
        return OAuthCredentials(
            refresh_token=refresh_token,
            client_id=self._client_id,
            client_secret=self._client_secret,
            user_email=user_email,
        )


class CredentialsResolverProtocol(Protocol):
    """Shape both ``CredentialsResolver`` and ``StubCredentialsResolver`` honor.

    Lets the handler stay provider-agnostic — it only depends on this Protocol,
    not on a concrete resolver type.
    """

    def resolve(self, credentials_ref: str) -> OAuthCredentials: ...


class StubCredentialsResolver:
    """No-op resolver for ``EMAIL_PROVIDER=stub`` local runs.

    Returns trivial OAuthCredentials regardless of ``credentials_ref``. Has the
    same ``resolve()`` shape as ``CredentialsResolver`` (duck-typed via
    ``CredentialsResolverProtocol``).
    """

    def resolve(self, credentials_ref: str) -> OAuthCredentials:
        return OAuthCredentials(
            refresh_token="stub", client_id="stub", client_secret="stub",
        )
