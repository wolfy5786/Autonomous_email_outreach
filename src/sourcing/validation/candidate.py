"""
Candidate validation gate — between Phase 1 (discovery) and Phase 2 (enrichment).

Implements the minimum-viable filtering described in ``docs/data-sourcing-service.md`` §8.1:
domain sanity, in-run deduplication with Tier A preference, and Tier-B-vs-Tier-A
cross-check. ICP relevance, blocklist, and MX/DNS checks are deferred (TODO).
"""

from __future__ import annotations

import re
from typing import Any

from shared.models.plan import PlanRecord


_HOSTNAME_RE = re.compile(r"^[a-z0-9][a-z0-9\-]*(\.[a-z0-9][a-z0-9\-]*)+$")
_IPV4_RE = re.compile(r"^\d+\.\d+\.\d+\.\d+$")
_RESERVED_DOMAINS: frozenset[str] = frozenset(
    {"localhost", "example.com", "example.org", "example.net", "test.com"}
)


def _normalize_domain(value: Any) -> str | None:
    """Lowercase hostname; strip scheme, ``www.`` prefix, path."""
    if not isinstance(value, str):
        return None
    s = value.strip().lower()
    s = re.sub(r"^https?://", "", s)
    s = s.split("/")[0]
    if s.startswith("www."):
        s = s[4:]
    if not s or "." not in s:
        return None
    return s


def _is_valid_domain(domain: str) -> bool:
    if not domain or "." not in domain:
        return False
    if domain in _RESERVED_DOMAINS:
        return False
    if _IPV4_RE.match(domain):
        return False
    return bool(_HOSTNAME_RE.match(domain))


def _candidate_tier(c: dict[str, Any]) -> str:
    return c.get("_discovery_tier") or ""


def validate_candidates(
    candidates: list[dict[str, Any]],
    plan: PlanRecord,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Partition raw discovery candidates into ``(accepted, rejected)``.

    Implemented gates:
    - **Domain sanity** — valid hostname, no IP, no reserved/parking domain.
    - **In-run dedup** — group by normalized domain; Tier A beats Tier B; first wins among ties.
      Duplicate sources are recorded under ``_aliases`` on the surviving candidate.
    - **Tier B cross-check** — Tier B candidates accepted only if their domain matches a
      Tier A candidate from the same run (per data_sourcing_map.md "Tier B" rule).

    Deferred (TODO):
    - ICP relevance vs ``plan.company_signals``.
    - Blocklist (excluded competitors / industries / regions).
    - MX / DNS sanity.

    :param candidates: Raw dicts from ``DiscoveryResult.candidates`` (with ``_discovery_source``
        and ``_discovery_tier`` injected by the pipeline).
    :param plan: Active plan; reserved for future ICP / blocklist gates.
    :returns: ``(accepted, rejected)``. Rejected dicts carry ``_reject_reason``.
    """
    rejected: list[dict[str, Any]] = []
    sanitized: list[dict[str, Any]] = []

    for c in candidates:
        domain = _normalize_domain(c.get("domain"))
        if not domain or not _is_valid_domain(domain):
            rejected.append({**c, "_reject_reason": "bad_domain"})
            continue
        c["domain"] = domain
        sanitized.append(c)

    tier_a_domains: set[str] = {c["domain"] for c in sanitized if _candidate_tier(c) == "A"}

    by_domain: dict[str, dict[str, Any]] = {}
    for c in sanitized:
        d = c["domain"]
        existing = by_domain.get(d)
        if existing is None:
            by_domain[d] = c
            continue
        existing_tier = _candidate_tier(existing)
        new_tier = _candidate_tier(c)
        keep_existing = existing_tier == "A" or new_tier != "A"
        loser = c if keep_existing else existing
        winner = existing if keep_existing else c
        winner.setdefault("_aliases", []).append(loser.get("_discovery_source"))
        if not keep_existing:
            by_domain[d] = winner

    accepted: list[dict[str, Any]] = []
    for d, c in by_domain.items():
        if _candidate_tier(c) == "B" and d not in tier_a_domains:
            rejected.append({**c, "_reject_reason": "tier_b_no_tier_a_match"})
            continue
        accepted.append(c)

    return accepted, rejected


if __name__ == "__main__":
    from collections import Counter

    yc_a = {
        "name": "Acme",
        "domain": "acme.com",
        "_discovery_source": "yc_directory",
        "_discovery_tier": "A",
    }
    yc_b = {
        "name": "Bravo",
        "domain": "bravo.io",
        "_discovery_source": "yc_directory",
        "_discovery_tier": "A",
    }
    yc_dup = {
        "name": "Acme Inc",
        "domain": "ACME.COM",
        "_discovery_source": "yc_directory",
        "_discovery_tier": "A",
    }
    hn_match = {
        "name": "Acme",
        "domain": "https://acme.com/launch",
        "_discovery_source": "hacker_news",
        "_discovery_tier": "B",
    }
    hn_orphan = {
        "name": "Charlie",
        "domain": "charlie.app",
        "_discovery_source": "hacker_news",
        "_discovery_tier": "B",
    }
    bad_local = {
        "name": "Local",
        "domain": "localhost",
        "_discovery_source": "hacker_news",
        "_discovery_tier": "B",
    }
    bad_ip = {
        "name": "IP",
        "domain": "192.168.1.1",
        "_discovery_source": "yc_directory",
        "_discovery_tier": "A",
    }
    bad_none = {
        "name": "None",
        "domain": None,
        "_discovery_source": "yc_directory",
        "_discovery_tier": "A",
    }

    fixtures = [yc_a, yc_b, yc_dup, hn_match, hn_orphan, bad_local, bad_ip, bad_none]

    class _StubPlan:
        company_signals: list[str] = []

    accepted, rejected = validate_candidates(fixtures, _StubPlan())  # type: ignore[arg-type]

    print(f"input={len(fixtures)} accepted={len(accepted)} rejected={len(rejected)}")
    print("\nAccepted:")
    for c in accepted:
        print(
            f"  {c['domain']:18s}  tier={c.get('_discovery_tier')}"
            f"  src={c.get('_discovery_source')}  aliases={c.get('_aliases', [])}"
        )
    print("\nRejected:")
    for c in rejected:
        print(
            f"  {str(c.get('domain'))!r:18s}  reason={c.get('_reject_reason')}"
            f"  src={c.get('_discovery_source')}"
        )
    print("\nReject reason counts:", dict(Counter(c["_reject_reason"] for c in rejected)))
