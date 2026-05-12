from messaging.config import settings

from .base import EmailDraftProvider
from .gmail import GmailDraftProvider
from .stub import StubDraftProvider


def create_provider(name: str | None = None) -> EmailDraftProvider:
    """Pick a provider by name (defaults to ``settings.email_provider``)."""
    chosen = (name or settings.email_provider).strip().lower()
    if chosen == "stub":
        return StubDraftProvider()
    if chosen == "gmail":
        return GmailDraftProvider()
    raise ValueError(f"Unsupported EMAIL_PROVIDER={chosen!r}. Expected 'stub' or 'gmail'.")
