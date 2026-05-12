"""
Shared code for email_outreach services.

Subpackages are imported explicitly by callers (``from shared.models import ...``,
``from shared.observability import ...``) — this top-level package intentionally
performs no eager imports, so services that don't need ``shared.models`` (and
therefore don't install ``beanie``) can still use ``shared.observability``.
"""
