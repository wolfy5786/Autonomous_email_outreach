"""Product Hunt — Tier A primary for software (SW only).

Unit tests for plan filter helpers and discovery behavior::

    PYTHONPATH=src:src/sourcing pytest src/sourcing/tests/test_product_hunt_plan_filters.py -q
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

import httpx

from discovery.base import DiscoveryContext, DiscoveryResult, DiscoverySource
from shared.models.plan import ProductHuntFilters, ProductHuntSource

logger = logging.getLogger("sourcing.discovery.product_hunt")

DEFAULT_API_URL = "https://api.producthunt.com/v2/api/graphql"

# postedAfter is optional: some schema revisions omit it — we retry without and use client-side lookback.
_GRAPHQL_POST_SELECTION = """
    totalCount
    pageInfo {
      hasNextPage
      endCursor
    }
    edges {
      node {
        id
        name
        slug
        tagline
        description
        votesCount
        createdAt
        featuredAt
        url
        website
        topics(first: 10) {
          edges {
            node {
              id
              name
              slug
            }
          }
        }
        makers {
          id
          name
          username
        }
      }
    }
"""

GRAPHQL_DISCOVER_POSTS = (
    """
query DiscoverPosts($first: Int!, $after: String, $postedAfter: DateTime, $postedBefore: DateTime, $topic: String, $order: PostsOrder) {
  posts(first: $first, after: $after, postedAfter: $postedAfter, postedBefore: $postedBefore, topic: $topic, order: $order) {
"""
    + _GRAPHQL_POST_SELECTION
    + """
  }
}
"""
)

GRAPHQL_DISCOVER_POSTS_NO_POSTED_AFTER = (
    """
query DiscoverPosts($first: Int!, $after: String, $postedBefore: DateTime, $topic: String, $order: PostsOrder) {
  posts(first: $first, after: $after, postedBefore: $postedBefore, topic: $topic, order: $order) {
"""
    + _GRAPHQL_POST_SELECTION
    + """
  }
}
"""
)


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning(
            "stage=ph_env_invalid name=%s raw=%r using_default=%s",
            name,
            raw,
            default,
        )
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        return float(raw)
    except ValueError:
        logger.warning(
            "stage=ph_env_invalid name=%s raw=%r using_default=%s",
            name,
            raw,
            default,
        )
        return default


def _env_str(name: str, default: str) -> str:
    raw = os.environ.get(name)
    if raw is None or not str(raw).strip():
        return default
    return str(raw).strip()


def _env_optional_topic() -> str | None:
    raw = (os.environ.get("PRODUCT_HUNT_TOPIC") or "").strip()
    return raw or None


def _datetime_to_ph_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _resolve_posted_before_iso() -> str | None:
    """
    Upper bound for posts (GraphQL postedBefore). ISO env wins over *_DAYS when both set.
    """
    iso_raw = (os.environ.get("PRODUCT_HUNT_POSTED_BEFORE") or "").strip()
    if iso_raw:
        dt = _parse_iso(iso_raw)
        if dt is None:
            logger.warning(
                "stage=ph_env_invalid name=PRODUCT_HUNT_POSTED_BEFORE raw=%r",
                iso_raw,
            )
            return None
        return _datetime_to_ph_iso(dt)

    days_raw = (os.environ.get("PRODUCT_HUNT_POSTED_BEFORE_DAYS") or "").strip()
    if not days_raw:
        return None
    try:
        days = int(days_raw)
    except ValueError:
        logger.warning(
            "stage=ph_env_invalid name=PRODUCT_HUNT_POSTED_BEFORE_DAYS raw=%r",
            days_raw,
        )
        return None
    if days < 1:
        logger.warning(
            "stage=ph_env_invalid name=PRODUCT_HUNT_POSTED_BEFORE_DAYS raw=%r using_default=unset min_allowed=1",
            days_raw,
        )
        return None
    boundary = datetime.now(timezone.utc) - timedelta(days=days)
    return boundary.strftime("%Y-%m-%dT%H:%M:%SZ")


def _product_hunt_block_from_plan(plan: Any) -> ProductHuntSource | None:
    sources = getattr(plan, "sources", None)
    if not isinstance(sources, list):
        return None
    for block in sources:
        if isinstance(block, ProductHuntSource):
            return block
        if getattr(block, "source", None) == "product_hunt":
            return ProductHuntSource.model_validate(block)
    return None


def _topic_slug_for_api(topic: str) -> str:
    """Map plan topic labels (e.g. ``Developer Tools``) to PH-style slugs (``developer-tools``)."""
    t = " ".join(topic.strip().split())
    if not t:
        return ""
    return "-".join(part.lower() for part in t.split() if part)


def _topics_for_api_queries(filters: ProductHuntFilters | None, env_topic: str | None) -> list[str | None]:
    """
    GraphQL accepts one ``topic`` per query. Returns a list of topic strings or ``None``
    for a single unfiltered run.
    """
    if filters and filters.topics:
        slugs: list[str | None] = []
        for raw in filters.topics:
            if not isinstance(raw, str):
                continue
            slug = _topic_slug_for_api(raw)
            if slug:
                slugs.append(slug)
        if slugs:
            return slugs
    if env_topic and env_topic.strip():
        return [env_topic.strip()]
    return [None]


def _date_start_utc(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)


def _plan_posted_before_to_dt_upper_bound(d: date) -> datetime:
    """Inclusive end of ``d`` in UTC for ``postedBefore``-style filtering."""
    return datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=timezone.utc)


def merge_ph_time_bounds(
    *,
    now_utc: datetime,
    lookback_days: int,
    env_posted_before_iso: str | None,
    plan_posted_after: date | None,
    plan_posted_before: date | None,
) -> tuple[datetime, str, str | None]:
    """
    Stricter window: latest effective ``postedAfter`` (``cutoff``), earliest ``postedBefore``.
    Returns ``(cutoff_dt, posted_after_iso, posted_before_iso)``.
    """
    env_cutoff = now_utc - timedelta(days=lookback_days)
    if plan_posted_after is not None:
        plan_start = _date_start_utc(plan_posted_after)
        cutoff = max(env_cutoff, plan_start)
    else:
        cutoff = env_cutoff
    posted_after_iso = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")

    before_candidates: list[datetime] = []
    if env_posted_before_iso:
        env_dt = _parse_iso(env_posted_before_iso)
        if env_dt is not None:
            if env_dt.tzinfo is None:
                env_dt = env_dt.replace(tzinfo=timezone.utc)
            else:
                env_dt = env_dt.astimezone(timezone.utc)
            before_candidates.append(env_dt)
    if plan_posted_before is not None:
        before_candidates.append(_plan_posted_before_to_dt_upper_bound(plan_posted_before))

    posted_before_iso: str | None
    if not before_candidates:
        posted_before_iso = None
    else:
        earliest = min(before_candidates)
        posted_before_iso = _datetime_to_ph_iso(earliest)

    return cutoff, posted_after_iso, posted_before_iso


def _resolve_min_upvotes(plan_min: int | None, env_min: int) -> int:
    if plan_min is None:
        return env_min
    return max(plan_min, env_min)


def _dedupe_candidates_by_domain(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_domain: dict[str, dict[str, Any]] = {}
    for c in candidates:
        domain = c.get("domain")
        if not isinstance(domain, str) or not domain:
            continue
        if domain not in by_domain:
            by_domain[domain] = c
    return list(by_domain.values())


def _resolve_bearer_token() -> tuple[str | None, str | None]:
    oauth = (os.environ.get("PRODUCT_HUNT_TOKEN") or "").strip()
    if oauth:
        return oauth, "oauth"
    dev = (os.environ.get("PRODUCT_HUNT_DEVELOPER_TOKEN") or "").strip()
    if dev:
        return dev, "developer"
    return None, None


def _rate_limit_headers(resp: httpx.Response) -> dict[str, str | None]:
    h = resp.headers
    return {
        "limit": h.get("x-ratelimit-limit") or h.get("X-RateLimit-Limit"),
        "remaining": h.get("x-ratelimit-remaining") or h.get("X-RateLimit-Remaining"),
        "reset": h.get("x-ratelimit-reset") or h.get("X-RateLimit-Reset"),
    }


def _body_preview(text: str, max_len: int = 500) -> str:
    t = text if len(text) <= max_len else text[:max_len] + "…"
    return t.replace("\n", "\\n")


def _sleep_retry_after(resp: httpx.Response) -> float:
    ra = resp.headers.get("retry-after") or resp.headers.get("Retry-After")
    if ra:
        try:
            return float(ra)
        except ValueError:
            pass
    rh = _rate_limit_headers(resp)
    reset = rh.get("reset")
    if reset:
        try:
            v = float(reset)
            if v > 1e10:
                now = time.time()
                return max(0.0, v - now)
            return max(0.0, v)
        except ValueError:
            pass
    return 60.0


def _parse_iso(dt_val: Any) -> datetime | None:
    if dt_val is None:
        return None
    if not isinstance(dt_val, str):
        return None
    s = dt_val.strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        logger.debug("stage=ph_date_parse_failed raw=%r", dt_val)
        return None


def _hostname_from_url(url: str | None) -> str | None:
    if not url or not isinstance(url, str):
        return None
    u = url.strip()
    if not u:
        return None
    parsed = urlparse(u)
    host = parsed.hostname
    if not host and "://" not in u and "/" not in u and "." in u:
        h = u.lower().split("/")[0]
        if h.startswith("www."):
            h = h[4:]
        return h or None
    if not host:
        return None
    host = host.lower()
    if host.startswith("www."):
        host = host[4:]
    return host or None


def _topics_slugs(node: dict[str, Any]) -> list[str]:
    topics = node.get("topics")
    if not isinstance(topics, dict):
        return []
    edges = topics.get("edges")
    if not isinstance(edges, list):
        return []
    slugs: list[str] = []
    for e in edges:
        if not isinstance(e, dict):
            continue
        n = e.get("node")
        if isinstance(n, dict):
            slug = n.get("slug")
            if isinstance(slug, str) and slug:
                slugs.append(slug)
    return slugs


def _makers_list(node: dict[str, Any]) -> list[dict[str, Any]]:
    makers = node.get("makers")
    if not isinstance(makers, list):
        return []
    out: list[dict[str, Any]] = []
    for m in makers:
        if not isinstance(m, dict):
            continue
        out.append(
            {
                "id": m.get("id"),
                "name": m.get("name"),
                "username": m.get("username"),
            }
        )
    return out


def _node_to_candidate(
    node: dict[str, Any],
    cutoff: datetime,
    min_upvotes: int = 0,
) -> dict[str, Any] | None:
    node_id = node.get("id")
    slug = node.get("slug")

    featured_at = _parse_iso(node.get("featuredAt"))
    created_at = _parse_iso(node.get("createdAt"))
    launch_dt = featured_at or created_at
    if launch_dt is None:
        logger.debug(
            "stage=ph_candidate_skipped node_id=%s slug=%s reason=no_launch_date",
            node_id,
            slug,
        )
        return None
    if launch_dt.tzinfo is None:
        launch_dt = launch_dt.replace(tzinfo=timezone.utc)
    else:
        launch_dt = launch_dt.astimezone(timezone.utc)

    if launch_dt < cutoff:
        logger.debug(
            "stage=ph_candidate_skipped node_id=%s slug=%s reason=outside_lookback launch=%s",
            node_id,
            slug,
            launch_dt.isoformat(),
        )
        return None

    website_raw = node.get("website")
    website_url: str | None
    if isinstance(website_raw, str):
        website_url = website_raw.strip() or None
    else:
        website_url = None

    domain = _hostname_from_url(website_url)
    if not domain:
        logger.debug(
            "stage=ph_candidate_skipped node_id=%s slug=%s reason=no_domain website=%r",
            node_id,
            slug,
            website_url,
        )
        return None

    name = node.get("name")
    if not isinstance(name, str) or not name.strip():
        logger.debug(
            "stage=ph_candidate_skipped node_id=%s slug=%s reason=no_name",
            node_id,
            slug,
        )
        return None

    tagline = node.get("tagline") if isinstance(node.get("tagline"), str) else None
    desc = node.get("description") if isinstance(node.get("description"), str) else None
    description = (tagline or "").strip() or (desc or None)

    votes = node.get("votesCount")
    try:
        upvotes = int(votes) if votes is not None else 0
    except (TypeError, ValueError):
        upvotes = 0

    if upvotes < min_upvotes:
        logger.debug(
            "stage=ph_candidate_skipped node_id=%s slug=%s reason=below_min_upvotes upvotes=%s min=%s",
            node_id,
            slug,
            upvotes,
            min_upvotes,
        )
        return None

    ph_url = node.get("url") if isinstance(node.get("url"), str) else None

    return {
        "name": name.strip(),
        "domain": domain,
        "website_url": website_url,
        "description": description,
        "product_hunt_launch_date": launch_dt.isoformat(),
        "product_hunt_upvotes": upvotes,
        "tags": _topics_slugs(node),
        "product_hunt_slug": slug if isinstance(slug, str) else None,
        "product_hunt_url": ph_url,
        "makers": _makers_list(node),
    }


async def _throttle_between_pages(min_interval_s: float, last_mono: float | None) -> None:
    if last_mono is None:
        return
    elapsed = time.monotonic() - last_mono
    need = max(0.0, min_interval_s - elapsed)
    if need > 0:
        logger.info(
            "stage=ph_rate_limit_sleep sleep_s=%s reason=min_interval_between_pages",
            need,
        )
        await asyncio.sleep(need)


async def _post_graphql(
    client: httpx.AsyncClient,
    api_url: str,
    bearer: str,
    query: str,
    variables: dict[str, Any],
    page: int,
    max_retries_429: int,
) -> tuple[dict[str, Any] | None, httpx.Response | None, list[str]]:
    errs: list[str] = []
    attempt = 0
    while True:
        logger.info(
            "stage=ph_request page=%s attempt=%s variable_keys=%s",
            page,
            attempt,
            sorted(variables.keys()),
        )
        try:
            resp = await client.post(
                api_url,
                json={"query": query, "variables": variables},
                headers={
                    "Authorization": f"Bearer {bearer}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
            )
        except httpx.RequestError as e:
            errs.append(f"request_error:{e!r}")
            logger.warning(
                "stage=ph_request_failed page=%s error=%s",
                page,
                e,
                exc_info=True,
            )
            return None, None, errs

        rh = _rate_limit_headers(resp)
        logger.info(
            "stage=ph_response page=%s status=%s ratelimit_limit=%s ratelimit_remaining=%s ratelimit_reset=%s",
            page,
            resp.status_code,
            rh.get("limit"),
            rh.get("remaining"),
            rh.get("reset"),
        )

        if resp.status_code == 429 and attempt < max_retries_429:
            sleep_s = _sleep_retry_after(resp)
            logger.warning(
                "stage=ph_rate_limited page=%s attempt=%s sleep_s=%s",
                page,
                attempt,
                sleep_s,
            )
            await asyncio.sleep(sleep_s)
            attempt += 1
            continue

        if resp.status_code >= 400:
            text = resp.text
            errs.append(f"http_{resp.status_code}:{_body_preview(text)}")
            logger.warning(
                "stage=ph_http_error page=%s status=%s body_preview=%r",
                page,
                resp.status_code,
                _body_preview(text),
            )
            return None, resp, errs

        try:
            payload: dict[str, Any] = resp.json()
        except json.JSONDecodeError as e:
            text = resp.text
            errs.append(f"json_decode:{e!r}")
            logger.warning(
                "stage=ph_json_decode_failed page=%s error=%s body_preview=%r",
                page,
                e,
                _body_preview(text),
            )
            return None, resp, errs

        return payload, resp, errs


async def _run_ph_pagination(
    *,
    client: httpx.AsyncClient,
    api_url: str,
    token: str,
    topic_slug: str | None,
    posted_after_iso: str,
    posted_before_iso: str | None,
    page_size: int,
    max_pages: int,
    order: str,
    min_interval_s: float,
    max_retries_429: int,
    cutoff: datetime,
    min_upvotes: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Fetch paginated posts for one GraphQL ``topic`` value (``None`` = all topics)."""
    errors: list[str] = []
    candidates: list[dict[str, Any]] = []
    include_posted_after = True
    cursor: str | None = None
    last_mono: float | None = None

    for page in range(1, max_pages + 1):
        await _throttle_between_pages(min_interval_s, last_mono)

        variables_base: dict[str, Any] = {
            "first": page_size,
            "after": cursor,
            "postedBefore": posted_before_iso,
            "topic": topic_slug,
            "order": order,
        }
        variables_with = {**variables_base, "postedAfter": posted_after_iso}
        variables_without = dict(variables_base)

        payload: dict[str, Any] | None = None
        post_errs: list[str] = []

        max_gql_attempts = 2 if include_posted_after else 1
        for gql_retry in range(max_gql_attempts):
            use_posted = include_posted_after and gql_retry == 0
            q = GRAPHQL_DISCOVER_POSTS if use_posted else GRAPHQL_DISCOVER_POSTS_NO_POSTED_AFTER
            vars_ = variables_with if use_posted else variables_without

            payload, _resp, post_errs = await _post_graphql(
                client,
                api_url,
                token,
                q,
                vars_,
                page,
                max_retries_429,
            )
            errors.extend(post_errs)
            last_mono = time.monotonic()

            if not payload:
                logger.warning(
                    "stage=ph_pagination_stop page=%s reason=http_or_transport_error topic=%r",
                    page,
                    topic_slug,
                )
                break

            gql_err_list = payload.get("errors")
            if gql_err_list and use_posted:
                logger.warning(
                    "stage=ph_graphql_errors page=%s errors=%s retrying_without_posted_after=true topic=%r",
                    page,
                    gql_err_list[:3],
                    topic_slug,
                )
                include_posted_after = False
                continue

            if gql_err_list:
                logger.warning(
                    "stage=ph_graphql_errors page=%s errors=%s topic=%r",
                    page,
                    gql_err_list[:3],
                    topic_slug,
                )
                errors.append(f"graphql_errors:{gql_err_list[:3]!r}")
                logger.warning(
                    "stage=ph_pagination_stop page=%s reason=graphql_errors topic=%r",
                    page,
                    topic_slug,
                )
                payload = None
                break

            break

        if not payload:
            break

        data = payload.get("data") or {}
        posts_conn = data.get("posts")
        if not isinstance(posts_conn, dict):
            errors.append("product_hunt: missing data.posts")
            logger.warning(
                "stage=ph_pagination_stop page=%s reason=missing_posts_connection topic=%r",
                page,
                topic_slug,
            )
            break

        edges = posts_conn.get("edges")
        if not isinstance(edges, list):
            edges = []

        page_info = posts_conn.get("pageInfo") if isinstance(posts_conn.get("pageInfo"), dict) else {}
        has_next = bool(page_info.get("hasNextPage"))
        end_cursor = page_info.get("endCursor")
        next_cursor: str | None = end_cursor if isinstance(end_cursor, str) else None

        total_count = posts_conn.get("totalCount")

        logger.info(
            "stage=ph_page_decoded page=%s edges_count=%s total_count=%s has_next=%s topic=%r",
            page,
            len(edges),
            total_count,
            has_next,
            topic_slug,
        )

        page_added = 0
        for edge in edges:
            if not isinstance(edge, dict):
                continue
            node = edge.get("node")
            if not isinstance(node, dict):
                continue
            cand = _node_to_candidate(node, cutoff, min_upvotes)
            if cand is not None:
                candidates.append(cand)
                page_added += 1

        logger.info(
            "stage=ph_page_done page=%s candidates_added=%s running_total=%s topic=%r",
            page,
            page_added,
            len(candidates),
            topic_slug,
        )

        if not has_next or not next_cursor:
            logger.info(
                "stage=ph_pagination_stop page=%s reason=no_next_page topic=%r",
                page,
                topic_slug,
            )
            break

        cursor = next_cursor

    return candidates, errors


class ProductHuntDiscovery(DiscoverySource):
    """
    Free API + HTML fallback. Launch date, upvotes, tags, maker info, website.

    Best for recent software launches (last 24 months); upvotes as traction proxy.
    """

    source_name = "product_hunt"
    tier = "A"
    verticals = ["SW"]

    async def discover(self, ctx: DiscoveryContext) -> DiscoveryResult:
        block = _product_hunt_block_from_plan(ctx.plan)
        if block is not None and not block.enabled:
            logger.info(
                "stage=ph_skipped_disabled campaign_id=%s reason=plan_enabled_false",
                ctx.campaign_id,
            )
            return DiscoveryResult(source_name=self.source_name, tier=self.tier, candidates=[], errors=[])

        ph_filters: ProductHuntFilters | None = block.filters if block is not None else None
        if block is None:
            logger.info(
                "stage=ph_no_plan_block campaign_id=%s note=env_defaults",
                ctx.campaign_id,
            )

        errors: list[str] = []
        candidates: list[dict[str, Any]] = []

        token, token_mode = _resolve_bearer_token()
        if not token:
            logger.error(
                "stage=ph_token_missing campaign_id=%s tried=[oauth,developer]",
                ctx.campaign_id,
            )
            return DiscoveryResult(
                source_name=self.source_name,
                tier=self.tier,
                candidates=[],
                errors=[
                    "product_hunt: no token; set PRODUCT_HUNT_TOKEN or PRODUCT_HUNT_DEVELOPER_TOKEN",
                ],
            )

        logger.info(
            "stage=ph_token_resolved campaign_id=%s mode=%s",
            ctx.campaign_id,
            token_mode,
        )

        api_url = _env_str("PRODUCT_HUNT_API_URL", DEFAULT_API_URL)
        page_size = max(1, min(20, _env_int("PRODUCT_HUNT_PAGE_SIZE", 20)))
        max_pages = max(1, _env_int("PRODUCT_HUNT_MAX_PAGES", 5))
        lookback_days = max(1, _env_int("PRODUCT_HUNT_LOOKBACK_DAYS", 180))
        order = _env_str("PRODUCT_HUNT_ORDER", "VOTES")
        timeout_s = max(5.0, _env_float("PRODUCT_HUNT_REQUEST_TIMEOUT_S", 20.0))
        min_interval_s = max(0.0, _env_float("PRODUCT_HUNT_MIN_INTERVAL_S", 1.0))
        max_retries_429 = max(0, _env_int("PRODUCT_HUNT_MAX_RETRIES_429", 1))
        env_min_upvotes = max(0, _env_int("PRODUCT_HUNT_MIN_UPVOTES", 0))
        min_upvotes = _resolve_min_upvotes(
            ph_filters.min_votes if ph_filters else None,
            env_min_upvotes,
        )
        env_topic = _env_optional_topic()
        env_posted_before_iso = _resolve_posted_before_iso()

        now_utc = datetime.now(timezone.utc)
        plan_after = ph_filters.posted_after if ph_filters else None
        plan_before = ph_filters.posted_before if ph_filters else None
        cutoff, posted_after_iso, posted_before_iso = merge_ph_time_bounds(
            now_utc=now_utc,
            lookback_days=lookback_days,
            env_posted_before_iso=env_posted_before_iso,
            plan_posted_after=plan_after,
            plan_posted_before=plan_before,
        )
        topic_queries = _topics_for_api_queries(ph_filters, env_topic)

        logger.info(
            "stage=ph_start campaign_id=%s page_size=%s max_pages=%s lookback_days=%s order=%s "
            "posted_after=%s posted_before=%s topic_queries=%s min_upvotes=%s cutoff=%s",
            ctx.campaign_id,
            page_size,
            max_pages,
            lookback_days,
            order,
            posted_after_iso,
            posted_before_iso,
            topic_queries,
            min_upvotes,
            cutoff.isoformat(),
        )

        async with httpx.AsyncClient(timeout=timeout_s) as client:
            for topic_slug in topic_queries:
                part, part_errs = await _run_ph_pagination(
                    client=client,
                    api_url=api_url,
                    token=token,
                    topic_slug=topic_slug,
                    posted_after_iso=posted_after_iso,
                    posted_before_iso=posted_before_iso,
                    page_size=page_size,
                    max_pages=max_pages,
                    order=order,
                    min_interval_s=min_interval_s,
                    max_retries_429=max_retries_429,
                    cutoff=cutoff,
                    min_upvotes=min_upvotes,
                )
                candidates.extend(part)
                errors.extend(part_errs)

        candidates = _dedupe_candidates_by_domain(candidates)

        logger.info(
            "stage=ph_done campaign_id=%s total_candidates=%s errors_count=%s",
            ctx.campaign_id,
            len(candidates),
            len(errors),
        )

        return DiscoveryResult(
            source_name=self.source_name,
            tier=self.tier,
            candidates=candidates,
            errors=errors,
        )


def main() -> None:
    """
    Smoke-test Product Hunt discovery against plan filters (stub), env, and tokens.

    From repo ``src/sourcing`` layout (matches sourcing Docker ``PYTHONPATH``)::

        PYTHONPATH=../shared:. python -m discovery.product_hunt

    Uses a minimal stub ``plan`` with ``ProductHuntSource`` filters (no MongoDB).
    """
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Run Product Hunt discovery once (uses env / tokens).")
    parser.add_argument(
        "--campaign-id",
        default=os.environ.get("PRODUCT_HUNT_CLI_CAMPAIGN_ID", "cli-product-hunt"),
        help="DiscoveryContext.campaign_id (default: env PRODUCT_HUNT_CLI_CAMPAIGN_ID or cli-product-hunt)",
    )
    parser.add_argument(
        "--print-limit",
        type=int,
        default=20,
        metavar="N",
        help="Max candidates to print as JSON (default: 20)",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Log warnings only",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(levelname)s %(name)s %(message)s",
    )

    campaign_id = args.campaign_id.strip() or "cli-product-hunt"

    class _CliPlan:
        """Minimal stand-in for ``PlanRecord`` — only ``sources`` is read."""

        sources = [
            ProductHuntSource(
                source="product_hunt",
                enabled=True,
                filters=ProductHuntFilters(
                    topics=["Developer Tools", "SaaS"],
                    posted_after=date(2026, 1, 1),
                    min_votes=100,
                ),
            )
        ]

    ctx = DiscoveryContext(
        campaign_id=campaign_id,
        plan=_CliPlan(),  # type: ignore[arg-type]
    )

    result = asyncio.run(ProductHuntDiscovery().discover(ctx))

    sample = result.candidates[: max(0, args.print_limit)]
    summary = {
        "source_name": result.source_name,
        "tier": result.tier,
        "candidates_count": len(result.candidates),
        "errors": result.errors,
        "sample_candidates": sample,
    }
    print(json.dumps(summary, indent=2))

    if any("no token" in e for e in result.errors):
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
