from __future__ import annotations

from enum import StrEnum


class SourceType(StrEnum):
    """How / where a value or signal was produced (provenance, hints)."""

    API = "api"
    SERP = "serp"
    SCRAPE = "scrape"
    DIRECTORY = "directory"
    HINT_FEED = "hint_feed"


class FundingStage(StrEnum):
    BOOTSTRAPPED = "bootstrapped"
    SEED = "seed"
    SERIES_A = "series_a"
    SERIES_B = "series_b"
    GROWTH = "growth"
    PUBLIC = "public"
    UNKNOWN = "unknown"


class ScrapeMode(StrEnum):
    """Last scrape style applied to the company record (README data pipeline)."""

    ALL = "all"
    PARTIAL = "partial"
    NONE = "none"


class HintCategory(StrEnum):
    """Type of personalization signal stored as a hint."""

    FUNDING = "funding"
    HIRING = "hiring"
    PRODUCT_LAUNCH = "product_launch"
    TECH_STACK = "tech_stack"
    NEWS = "news"
    PARTNERSHIP = "partnership"
    EXPANSION = "expansion"
    CONTENT = "content"  # blog, podcast, talk
    OTHER = "other"


class DraftStatus(StrEnum):
    """Lifecycle of an email_draft_record (README §Data Schema)."""

    GENERATING = "generating"
    DRAFT_CREATED = "draft_created"
    FAILED = "failed"


class EmailProvider(StrEnum):
    """Email account provider used by Messaging Service."""

    GMAIL = "gmail"
    MICROSOFT = "microsoft"
    STUB = "stub"  # local/test only
