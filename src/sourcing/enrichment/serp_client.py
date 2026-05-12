"""SerpAPI client — used by operation 1 to discover a company's LinkedIn URL.

See ``design_docs/enrichment_redesign.md`` §1 ("SERP discovery"): the query is
``"{company_name}" LinkedIn`` and we pick the **first** organic result whose
host is on linkedin.com.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx

logger = logging.getLogger("sourcing.enrichment.serp")

SERPAPI_ENDPOINT = "https://serpapi.com/search.json"


@dataclass(frozen=True)
class SerpHit:
    url: str
    title: str | None = None
    snippet: str | None = None


class SerpAPIError(RuntimeError):
    """Raised when SerpAPI returns a non-2xx status or malformed payload."""


def _is_linkedin_url(url: str) -> bool:
    try:
        host = (urlparse(url).hostname or "").lower()
    except ValueError:
        return False
    if not host:
        return False
    return host == "linkedin.com" or host.endswith(".linkedin.com")


async def _serp_search_google(
    query: str,
    *,
    api_key: str,
    client: httpx.AsyncClient,
    num_results: int = 10,
    timeout_s: float = 30.0,
) -> list[SerpHit]:
    params = {
        "engine": "google",
        "q": query,
        "api_key": api_key,
        "num": num_results,
    }
    try:
        resp = await client.get(SERPAPI_ENDPOINT, params=params, timeout=timeout_s)
    except httpx.HTTPError as e:
        raise SerpAPIError(f"SerpAPI request failed: {e}") from e
    if resp.status_code != 200:
        raise SerpAPIError(f"SerpAPI returned status {resp.status_code}")
    try:
        data = resp.json()
    except ValueError as e:
        raise SerpAPIError(f"SerpAPI returned non-JSON payload: {e}") from e

    organic = data.get("organic_results") if isinstance(data, dict) else None
    if not isinstance(organic, list):
        return []

    hits: list[SerpHit] = []
    for row in organic:
        if not isinstance(row, dict):
            continue
        url = row.get("link")
        if not isinstance(url, str) or not url:
            continue
        title = row.get("title") if isinstance(row.get("title"), str) else None
        snippet = row.get("snippet") if isinstance(row.get("snippet"), str) else None
        hits.append(SerpHit(url=url, title=title, snippet=snippet))
    return hits


async def find_company_linkedin_url(
    company_name: str,
    *,
    api_key: str,
    client: httpx.AsyncClient,
    timeout_s: float = 30.0,
) -> SerpHit | None:
    """Return the first SERP hit whose URL is on linkedin.com, or ``None``."""
    query = f'"{company_name}" LinkedIn'
    hits = await _serp_search_google(
        query, api_key=api_key, client=client, timeout_s=timeout_s
    )
    for hit in hits:
        if _is_linkedin_url(hit.url):
            return hit
    return None
