"""YC directory client — used by operation 2 to fetch a company's YC profile.

See ``design_docs/enrichment_redesign.md`` §2. Operation 2 is intentionally
**light**: no SERP, no LLM, no full crawl4ai render. The YC directory is a
Next.js site that ships its full page data as a JSON blob inside a
``<script id="__NEXT_DATA__">`` tag, so a single ``httpx`` GET + JSON parse
is enough to recover the founders list and the most recent launch blurb.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import httpx

logger = logging.getLogger("sourcing.enrichment.yc_directory")

YC_COMPANY_URL_TEMPLATE = "https://www.ycombinator.com/companies/{slug}"

_SLUG_STRIP_RE = re.compile(r"[^a-z0-9\s_-]")
_SLUG_WS_RE = re.compile(r"[\s_]+")
_NEXT_DATA_RE = re.compile(
    r'<script[^>]+id="__NEXT_DATA__"[^>]*>(.*?)</script>',
    re.DOTALL,
)


class YCDirectoryError(RuntimeError):
    """Raised when the YC directory page is unreadable (network or parse)."""


@dataclass(frozen=True)
class YCFounder:
    full_name: str
    title: str | None = None


@dataclass(frozen=True)
class YCLatestNews:
    title: str
    url: str | None = None
    posted_at: datetime | None = None
    tagline: str | None = None


@dataclass(frozen=True)
class YCCompany:
    """Slice of YC company profile relevant to enrichment op 2."""

    profile_url: str
    name: str | None = None
    founders: list[YCFounder] = field(default_factory=list)
    latest_news: YCLatestNews | None = None


def yc_slug(company_name: str) -> str:
    """Build the YC directory slug for a company name.

    YC slugs are lowercase, hyphen-separated, alphanumerics + ``-`` only. We
    drop punctuation and collapse whitespace. This is a best-effort guess; a
    404 response from YC is the authoritative "not in directory" signal.
    """
    s = company_name.lower().strip()
    s = _SLUG_STRIP_RE.sub("", s)
    s = _SLUG_WS_RE.sub("-", s).strip("-")
    return s


def _extract_next_data(html: str) -> dict[str, Any] | None:
    m = _NEXT_DATA_RE.search(html)
    if not m:
        return None
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError as e:
        logger.warning("yc_directory: __NEXT_DATA__ JSON parse failed: %s", e)
        return None
    return data if isinstance(data, dict) else None


def _find_company_node(next_data: dict[str, Any]) -> dict[str, Any] | None:
    """Locate the company object inside Next.js page props.

    YC's directory has shifted shapes over time (``pageProps.company``,
    ``pageProps.initialState.company``, ...). We probe the common paths and
    fall back to ``None`` so the operation drops cleanly rather than crashes.
    """
    props = next_data.get("props")
    if not isinstance(props, dict):
        return None
    page_props = props.get("pageProps")
    if not isinstance(page_props, dict):
        return None

    candidates: list[Any] = [
        page_props.get("company"),
        page_props.get("data"),
        (page_props.get("initialState") or {}).get("company")
        if isinstance(page_props.get("initialState"), dict)
        else None,
    ]
    for c in candidates:
        if isinstance(c, dict) and (c.get("name") or c.get("slug") or c.get("founders")):
            return c
    return None


def _parse_founders(company_node: dict[str, Any]) -> list[YCFounder]:
    raw = company_node.get("founders")
    if not isinstance(raw, list):
        return []
    out: list[YCFounder] = []
    for row in raw:
        if not isinstance(row, dict):
            continue
        name = row.get("full_name") or row.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        title_val = row.get("title") or row.get("role")
        title = title_val.strip() if isinstance(title_val, str) and title_val.strip() else None
        out.append(YCFounder(full_name=name.strip(), title=title))
    return out


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    # YC commonly emits ISO-8601 with a "Z" suffix.
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _parse_latest_news(company_node: dict[str, Any]) -> YCLatestNews | None:
    """Pick the newest launch/news blurb. YC exposes these under several keys."""
    for key in ("launches", "news", "recent_launches", "company_launches"):
        raw = company_node.get(key)
        if not isinstance(raw, list) or not raw:
            continue
        entries: list[tuple[datetime | None, dict[str, Any]]] = []
        for row in raw:
            if not isinstance(row, dict):
                continue
            entries.append((_parse_datetime(row.get("created_at") or row.get("posted_at")), row))
        if not entries:
            continue
        # Sort by datetime desc; ``None`` sinks to the bottom.
        entries.sort(key=lambda kv: (kv[0] or datetime.min), reverse=True)
        _, row = entries[0]
        title = row.get("title") or row.get("name")
        if not isinstance(title, str) or not title.strip():
            continue
        url_val = row.get("url") or row.get("link")
        url = url_val if isinstance(url_val, str) and url_val else None
        tag_val = row.get("tagline") or row.get("body") or row.get("excerpt")
        tagline = tag_val.strip() if isinstance(tag_val, str) and tag_val.strip() else None
        posted = _parse_datetime(row.get("created_at") or row.get("posted_at"))
        return YCLatestNews(title=title.strip(), url=url, posted_at=posted, tagline=tagline)
    return None


def parse_yc_company_html(html: str, *, profile_url: str) -> YCCompany | None:
    """Parse YC's company page HTML into the slice op 2 needs.

    Returns ``None`` when the page does not look like a YC company profile
    (e.g. directory landing page, search results, or a layout change that
    removed the __NEXT_DATA__ company node).
    """
    next_data = _extract_next_data(html)
    if next_data is None:
        return None
    company_node = _find_company_node(next_data)
    if company_node is None:
        return None
    name_val = company_node.get("name")
    name = name_val.strip() if isinstance(name_val, str) and name_val.strip() else None
    return YCCompany(
        profile_url=profile_url,
        name=name,
        founders=_parse_founders(company_node),
        latest_news=_parse_latest_news(company_node),
    )


async def fetch_yc_company(
    company_name: str,
    *,
    client: httpx.AsyncClient,
    timeout_s: float = 30.0,
) -> YCCompany | None:
    """Resolve a company's YC profile.

    Returns ``None`` cleanly when the company is not in YC's directory (HTTP
    404 on the slugged URL). Raises ``YCDirectoryError`` for unexpected HTTP
    failures so the operation can record them in ``errors``.
    """
    slug = yc_slug(company_name)
    if not slug:
        return None
    url = YC_COMPANY_URL_TEMPLATE.format(slug=slug)
    try:
        resp = await client.get(url, timeout=timeout_s, follow_redirects=True)
    except httpx.HTTPError as e:
        raise YCDirectoryError(f"YC directory request failed: {e}") from e
    if resp.status_code == 404:
        return None
    if resp.status_code != 200:
        raise YCDirectoryError(
            f"YC directory returned status {resp.status_code} for {url}"
        )
    return parse_yc_company_html(resp.text, profile_url=str(resp.url))
