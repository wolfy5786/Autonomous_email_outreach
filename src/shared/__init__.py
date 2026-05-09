"""
Shared code for email_outreach services (MongoDB models, etc.).
Import from the parent source root on ``PYTHONPATH`` (e.g. ``from shared.models import CompanyRecord``).
"""

from shared.models.db import init_db

__all__ = ("init_db",)
