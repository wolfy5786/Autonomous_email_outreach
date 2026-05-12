from abc import ABC, abstractmethod

from pydantic import BaseModel, ConfigDict

from messaging.schemas import EmailProvider


class OAuthCredentials(BaseModel):
    """OAuth 2.0 credentials for the user's email account.

    Lives here (not in credentials.py) because it's the data shape the
    provider interface consumes. credentials.py (Step 7) imports + builds
    instances of this model from env vars / Secrets Manager.
    """

    model_config = ConfigDict(frozen=True)

    refresh_token: str
    client_id: str
    client_secret: str
    user_email: str = "me"   # provider-side user identifier; Gmail accepts "me"


class CreatedDraft(BaseModel):
    """Provider response — what the messaging service persists as `email_draft_ref`."""

    model_config = ConfigDict(frozen=True)

    provider: EmailProvider
    provider_draft_id: str


class EmailDraftProvider(ABC):
    """Strategy interface — one implementation per email account provider."""

    name: EmailProvider     # subclasses set this as a class attribute

    @abstractmethod
    async def create_draft(
        self,
        *,
        to: str,
        subject: str,
        body: str,
        oauth_credentials: OAuthCredentials,
    ) -> CreatedDraft:
        """Create a draft in the user's mailbox and return its provider id."""
