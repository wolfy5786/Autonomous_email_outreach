"""crawl4ai wrapper — single-page fetch with login-wall detection.

Per ``design_docs/enrichment_redesign.md`` operations must scrape exactly one
page (no navigation, no tabs, no internal-link following). Login walls cause
the operation to drop its slice for the company.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from urllib.parse import urlparse

logger = logging.getLogger("sourcing.enrichment.crawl")

# LinkedIn auth interstitials we know about. A redirect into any of these
# means the requested page was login-walled.
_LINKEDIN_AUTH_PATH_RE = re.compile(
    r"^/(authwall|login|uas/login|checkpoint(/|$)|signup)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class PageFetchResult:
    requested_url: str
    final_url: str
    markdown: str
    login_wall: bool


class CrawlError(RuntimeError):
    """Raised when crawl4ai fails or returns an unusable result."""


def _is_login_wall(final_url: str, markdown: str) -> bool:
    """Heuristic: redirect into an auth path, or the thin LinkedIn authwall body."""
    try:
        path = urlparse(final_url).path or ""
    except ValueError:
        path = ""
    if _LINKEDIN_AUTH_PATH_RE.search(path):
        return True
    if len(markdown) < 1200 and "Sign in" in markdown and (
        "Join now" in markdown or "Continue with" in markdown
    ):
        return True
    return False


async def fetch_single_page(url: str) -> PageFetchResult:
    """Single-page crawl4ai fetch. No navigation; no link-following."""
    try:
        from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
    except ImportError as e:  # pragma: no cover — runtime missing dep
        raise CrawlError(f"crawl4ai is not installed: {e}") from e

    run_config = CrawlerRunConfig(
        wait_for_images=False,
        process_iframes=False,
        excluded_tags=["script", "style", "noscript"],
    )
    try:
        async with AsyncWebCrawler() as crawler:
            result = await crawler.arun(url=url, config=run_config)
    except Exception as e:  # pragma: no cover — surface as CrawlError
        raise CrawlError(f"crawl4ai raised: {type(e).__name__}: {e}") from e

    if not getattr(result, "success", False):
        raise CrawlError(
            f"crawl4ai failed for {url}: {getattr(result, 'error_message', 'unknown')}"
        )

    final_url = getattr(result, "url", url) or url
    markdown_obj = getattr(result, "markdown", "") or ""
    markdown = markdown_obj if isinstance(markdown_obj, str) else str(markdown_obj)

    return PageFetchResult(
        requested_url=url,
        final_url=final_url,
        markdown=markdown,
        login_wall=_is_login_wall(final_url, markdown),
    )
