from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any


_TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)


def _tokens(s: str) -> set[str]:
    return set(_TOKEN_RE.findall(s.lower()))


def _stringify(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    if isinstance(v, (int, float, bool)):
        return str(v)
    if isinstance(v, (list, tuple, set)):
        return " ".join(_stringify(x) for x in v)
    if isinstance(v, dict):
        return " ".join(f"{k} {_stringify(val)}" for k, val in v.items())
    return str(v)


def _field_value(doc: dict[str, Any], key: str) -> Any:
    if key in doc:
        return doc.get(key)
    extra = doc.get("extra") or {}
    if isinstance(extra, dict) and key in extra:
        return extra.get(key)
    return None


def _soft_match_score(value: Any, signal: str) -> float:
    """
    Heuristic scoring for demo:
    - if signal tokens appear in doc field values → higher score
    - robust to semi-structured extra keys
    """
    s = _stringify(value)
    if not s:
        return 0.0
    q = signal.strip()
    if not q:
        return 0.0
    vtok = _tokens(s)
    qtok = _tokens(q)
    if not qtok:
        return 0.0
    overlap = len(vtok & qtok) / max(1, len(qtok))
    # small nonlinear boost for high overlap
    return math.sqrt(overlap)


@dataclass(frozen=True)
class PlanWeights:
    scoring_weights: dict[str, float]

    @classmethod
    def from_plan(cls, plan: dict[str, Any]) -> "PlanWeights":
        weights = plan.get("scoring_weights") or {}
        if not isinstance(weights, dict):
            weights = {}
        # normalize negative/NaN weights away (demo safety)
        out: dict[str, float] = {}
        for k, v in weights.items():
            try:
                fv = float(v)
            except Exception:
                continue
            if math.isnan(fv) or fv <= 0:
                continue
            out[str(k)] = fv
        return cls(scoring_weights=out)


def score_company(company: dict[str, Any], plan: dict[str, Any]) -> float:
    weights = PlanWeights.from_plan(plan).scoring_weights
    if not weights:
        return 0.0
    total_w = sum(weights.values())
    if total_w <= 0:
        return 0.0

    acc = 0.0
    for dim, w in weights.items():
        # dim might refer to core fields or arbitrary extra keys.
        v = _field_value(company, dim)
        # fallback: try matching against full doc text if key absent
        if v is None:
            v = company
        acc += w * _soft_match_score(v, dim)

    return max(0.0, min(1.0, acc / total_w))


def score_person(person: dict[str, Any], plan: dict[str, Any]) -> float:
    # For demo: reuse same weights, but apply to person record.
    weights = PlanWeights.from_plan(plan).scoring_weights
    if not weights:
        return 0.0
    total_w = sum(weights.values())
    if total_w <= 0:
        return 0.0

    acc = 0.0
    for dim, w in weights.items():
        v = _field_value(person, dim)
        if v is None:
            v = person
        acc += w * _soft_match_score(v, dim)

    return max(0.0, min(1.0, acc / total_w))


def combined_score(company_score: float, person_score: float) -> float:
    # simple, stable blend: company matters slightly more
    return max(0.0, min(1.0, 0.6 * company_score + 0.4 * person_score))

