import uuid

from messaging.schemas import EmailProvider

from .base import CreatedDraft, EmailDraftProvider, OAuthCredentials


class StubDraftProvider(EmailDraftProvider):
    """In-process stub — used for unit tests and ``EMAIL_PROVIDER=stub`` local runs.

    Does not call any external service. Returns a uuid-suffixed id with the
    ``stub-`` prefix so logs and downstream events make it obvious that no real
    draft was written.
    """

    name = EmailProvider.STUB

    async def create_draft(
        self,
        *,
        to: str,
        subject: str,
        body: str,
        oauth_credentials: OAuthCredentials,
    ) -> CreatedDraft:
        return CreatedDraft(
            provider=EmailProvider.STUB,
            provider_draft_id=f"stub-{uuid.uuid4()}",
        )
