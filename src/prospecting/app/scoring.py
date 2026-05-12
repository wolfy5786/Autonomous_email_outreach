from __future__ import annotations

import math
import re
from dataclasses import dataclass
from collections import Counter
from typing import Any

SCORING_VERSION = "v1"
COMPANY_DIMENSIONS = [
    "industry_match",
    "company_size_match",
    "funding_stage_match",
    "geography_match",
    "tech_stack_match",
    "growth_signal_match",
    "personalization_signal_match",
    "data_completeness",
    "freshness",
]
POC_DIMENSIONS = [
    "title_match",
    "seniority_match",
    "department_match",
    "email_verified",
    "linkedin_present",
    "role_relevance",
    "personalization_signal_match",
]

_TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)
_RANGE_RE = re.compile(r"(?P<low>\d{1,6})\s*[-–]\s*(?P<high>\d{1,6})")


@dataclass(frozen=True)
class DimensionScore:
    score: float
    confidence: float
    reason: str


@dataclass(frozen=True)
class ScoringResult:
    score: float
    dimension_scores: dict[str, DimensionScore]
    scoring_version: str = SCORING_VERSION


@dataclass(frozen=True)
class SemanticSearchResult:
    matched_key: str
    matched_value: Any
    similarity: float
    reason: str


@dataclass(frozen=True)
class PlanWeights:
    scoring_weights: dict[str, float]

    @classmethod
    def from_plan(cls, plan: dict[str, Any]) -> "PlanWeights":
        weights = plan.get("scoring_weights") or {}
        if not isinstance(weights, dict):
            weights = {}
        out: dict[str, float] = {}
        for key, value in weights.items():
            try:
                weight = float(value)
            except Exception:
                continue
            if math.isnan(weight) or weight < 0:
                continue
            out[str(key)] = weight
        return cls(scoring_weights=out)


def _tokens(value: str) -> set[str]:
    return set(_TOKEN_RE.findall(value.lower()))


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, (list, tuple, set)):
        return " ".join(_stringify(item) for item in value)
    if isinstance(value, dict):
        return " ".join(f"{key} {_stringify(item)}" for key, item in value.items())
    return str(value)


def _normalize_text(value: Any) -> str:
    return " ".join(_tokens(_stringify(value)))


def _get_field(doc: dict[str, Any], names: list[str]) -> Any:
    for name in names:
        if name in doc:
            return doc.get(name)
    return None


def _extra_map(doc: dict[str, Any]) -> dict[str, Any]:
    extra = doc.get("extra") or {}
    return extra if isinstance(extra, dict) else {}


def _vectorize_text(value: str) -> Counter[str]:
    return Counter(_tokens(value))


def _cosine_similarity(left: Counter[str], right: Counter[str]) -> float:
    if not left or not right:
        return 0.0
    shared = set(left) & set(right)
    numerator = sum(left[token] * right[token] for token in shared)
    left_norm = math.sqrt(sum(weight * weight for weight in left.values()))
    right_norm = math.sqrt(sum(weight * weight for weight in right.values()))
    if left_norm <= 0 or right_norm <= 0:
        return 0.0
    return numerator / (left_norm * right_norm)


def semantic_search_extra(
    record: dict[str, Any],
    query: str,
    collection: str,
    campaign_id: str,
    minimum_similarity: float = 0.35,
) -> SemanticSearchResult | None:
    extra = _extra_map(record)
    if not extra:
        return None

    query_text = _stringify(query).strip()
    if not query_text:
        return None

    query_vector = _vectorize_text(query_text)
    best_result: SemanticSearchResult | None = None

    for key, value in extra.items():
        candidate_text = f"{key} {_stringify(value)}"
        candidate_vector = _vectorize_text(candidate_text)
        similarity = _cosine_similarity(query_vector, candidate_vector)
        if similarity < minimum_similarity:
            continue
        if best_result is not None and similarity <= best_result.similarity:
            continue
        best_result = SemanticSearchResult(
            matched_key=str(key),
            matched_value=value,
            similarity=round(similarity, 6),
            reason=(
                f"semantic_search_extra matched extra[{key!r}]={value!r} in {collection} "
                f"for campaign_id={campaign_id} with cosine similarity {similarity:.3f} against query {query_text!r}"
            ),
        )

    return best_result


def _plan_signal_text(signals: list[str], aliases: list[str], fallback: str) -> str:
    if not signals:
        return fallback
    alias_tokens = set()
    for alias in aliases:
        alias_tokens.update(_tokens(alias))
    matched = [signal for signal in signals if _tokens(signal) & alias_tokens]
    selected = matched or signals
    return " ".join(selected)


def _text_match_score(candidate: Any, target: str) -> tuple[float, float, str]:
    candidate_text = _normalize_text(candidate)
    target_text = _normalize_text(target)
    if not candidate_text or not target_text:
        return 0.0, 0.15, "missing data for direct match"

    if candidate_text == target_text:
        return 1.0, 0.98, f"exact match: {candidate!r}"

    candidate_tokens = _tokens(candidate_text)
    target_tokens = _tokens(target_text)
    if not candidate_tokens or not target_tokens:
        return 0.0, 0.2, "insufficient tokens for direct match"

    overlap = len(candidate_tokens & target_tokens) / max(1, len(target_tokens))
    if overlap <= 0:
        return 0.0, 0.35, f"no token overlap against target {target!r}"

    confidence = 0.55 + min(0.35, overlap * 0.35)
    reason = f"token overlap {sorted(candidate_tokens & target_tokens)} against target {target!r}"
    return round(min(1.0, overlap), 6), round(min(1.0, confidence), 6), reason


def _semantic_extra_score(record: dict[str, Any], target: str, aliases: list[str], collection: str, campaign_id: str) -> tuple[float, float, str]:
    if not target:
        return 0.0, 0.1, "no query available for semantic fallback"

    semantic_result = semantic_search_extra(record, target, collection, campaign_id)
    if semantic_result is None:
        return 0.0, 0.2, f"no semantic hit in extra for target {target!r}"

    confidence = min(0.9, 0.45 + semantic_result.similarity * 0.45)
    return semantic_result.similarity, round(confidence, 6), semantic_result.reason


def _numeric_bucket_score(value: Any, target_text: str) -> tuple[float, float, str]:
    if value is None:
        return 0.0, 0.15, "missing numeric value"

    try:
        number = float(value)
    except Exception:
        return 0.0, 0.2, f"non-numeric value {value!r}"

    range_match = _RANGE_RE.search(target_text)
    if range_match:
        low = float(range_match.group("low"))
        high = float(range_match.group("high"))
        if low <= number <= high:
            return 1.0, 0.95, f"{number:g} is within target range {low:g}-{high:g}"
        distance = min(abs(number - low), abs(number - high))
        scale = max(high - low, 1.0)
        score = max(0.0, 1.0 - min(1.0, distance / scale))
        confidence = 0.6 if score > 0 else 0.4
        return round(score, 6), confidence, f"{number:g} is outside target range {low:g}-{high:g}"

    tokens = _tokens(target_text)
    if {"small", "mid", "medium", "large", "enterprise"} & tokens:
        if number < 50 and "small" in tokens:
            return 1.0, 0.9, f"{number:g} matches small-company signal"
        if 50 <= number < 250 and ({"mid", "medium"} & tokens):
            return 1.0, 0.9, f"{number:g} matches mid-market signal"
        if 250 <= number < 1000 and "large" in tokens:
            return 1.0, 0.9, f"{number:g} matches large-company signal"
        if number >= 1000 and "enterprise" in tokens:
            return 1.0, 0.9, f"{number:g} matches enterprise signal"
        return 0.0, 0.6, f"{number:g} does not match categorical size signal {sorted(tokens)}"

    return 0.5, 0.55, f"numeric value {number:g} present without an explicit target range"


def _bool_score(value: Any, expected_true: bool, reason_true: str, reason_false: str) -> tuple[float, float, str]:
    if value is None:
        return 0.0, 0.15, "missing boolean value"
    actual = bool(value)
    if actual == expected_true:
        return 1.0, 0.98, reason_true
    return 0.0, 0.9, reason_false


def _data_completeness_score(doc: dict[str, Any], required_fields: list[str]) -> tuple[float, float, str]:
    present = 0
    for field in required_fields:
        value = doc.get(field)
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        if isinstance(value, (list, dict, set, tuple)) and not value:
            continue
        present += 1
    score = present / max(1, len(required_fields))
    confidence = 0.95 if required_fields else 0.5
    return round(score, 6), confidence, f"{present}/{len(required_fields)} core fields present"


def _freshness_score(doc: dict[str, Any]) -> tuple[float, float, str]:
    timestamp = doc.get("freshness_timestamp")
    if timestamp:
        return 1.0, 0.75, f"freshness_timestamp present: {timestamp!r}"
    extra = _extra_map(doc)
    fallback, confidence, reason = _semantic_extra_score(doc, "freshness recent updated timestamp", ["freshness", "timestamp", "updated"], "records", str(doc.get("campaign_id", "")))
    if fallback > 0:
        return fallback, confidence, reason
    return 0.0, 0.2, "freshness_timestamp missing"


def _dimension_result(
    *,
    dimension: str,
    score: float,
    confidence: float,
    reason: str,
) -> DimensionScore:
    return DimensionScore(score=round(max(0.0, min(1.0, score)), 6), confidence=round(max(0.0, min(1.0, confidence)), 6), reason=reason)


def _weighted_average(results: dict[str, DimensionScore], weights: dict[str, float]) -> float:
    total_weight = 0.0
    weighted_sum = 0.0
    for name, result in results.items():
        weight = float(weights.get(name, 1.0)) if weights.get(name, 1.0) is not None else 1.0
        if weight < 0:
            continue
        total_weight += weight
        weighted_sum += weight * result.score
    if total_weight <= 0:
        return 0.0
    return round(max(0.0, min(1.0, weighted_sum / total_weight)), 6)


def _company_dimension_scores(company: dict[str, Any], plan: dict[str, Any]) -> dict[str, DimensionScore]:
    company_signals = plan.get("company_signals") or []
    if not isinstance(company_signals, list):
        company_signals = []
    extra = _extra_map(company)

    industry_target = _plan_signal_text(company_signals, ["industry", "sector", "vertical"], "industry sector vertical")
    size_target = _plan_signal_text(company_signals, ["company_size", "size", "headcount", "employee_count"], "company size employee count")
    funding_target = _plan_signal_text(company_signals, ["funding_stage", "funding", "stage"], "funding stage")
    geography_target = _plan_signal_text(company_signals, ["geography", "location", "hq", "headquarters", "country", "city"], "geography location headquarters")
    stack_target = _plan_signal_text(company_signals, ["tech_stack", "stack", "technology", "tools"], "tech stack technology stack")
    growth_target = _plan_signal_text(company_signals, ["growth", "hiring", "expansion", "funding"], "growth hiring funding expansion")
    personalization_target = _plan_signal_text(company_signals, ["personalization", "hook", "signal", "context"], "personalization signal context")

    results: dict[str, DimensionScore] = {}

    industry = _get_field(company, ["industry", "sector", "vertical"])
    if industry is not None:
        score, confidence, reason = _text_match_score(industry, industry_target)
    else:
        score, confidence, reason = _semantic_extra_score(company, industry_target, ["industry", "sector", "vertical"], "companies", str(plan.get("campaign_id", "")))
    results["industry_match"] = _dimension_result(dimension="industry_match", score=score, confidence=confidence, reason=reason)

    size_value = _get_field(company, ["employee_count", "employees", "size", "headcount"])
    if size_value is not None:
        score, confidence, reason = _numeric_bucket_score(size_value, size_target)
    else:
        score, confidence, reason = _semantic_extra_score(company, size_target, ["company_size", "size", "headcount", "employees"], "companies", str(plan.get("campaign_id", "")))
    results["company_size_match"] = _dimension_result(dimension="company_size_match", score=score, confidence=confidence, reason=reason)

    funding_stage = _get_field(company, ["funding_stage", "stage"])
    if funding_stage is not None:
        score, confidence, reason = _text_match_score(funding_stage, funding_target)
    else:
        score, confidence, reason = _semantic_extra_score(company, funding_target, ["funding_stage", "funding", "stage"], "companies", str(plan.get("campaign_id", "")))
    results["funding_stage_match"] = _dimension_result(dimension="funding_stage_match", score=score, confidence=confidence, reason=reason)

    geography_value = _get_field(company, ["headquarters", "location", "geography", "country", "city"])
    if geography_value is not None:
        score, confidence, reason = _text_match_score(geography_value, geography_target)
    else:
        score, confidence, reason = _semantic_extra_score(company, geography_target, ["geography", "location", "hq", "headquarters", "country", "city"], "companies", str(plan.get("campaign_id", "")))
    results["geography_match"] = _dimension_result(dimension="geography_match", score=score, confidence=confidence, reason=reason)

    tech_stack = _get_field(company, ["tech_stack", "technology_stack", "stack"])
    if tech_stack is not None:
        score, confidence, reason = _text_match_score(tech_stack, stack_target)
    else:
        score, confidence, reason = _semantic_extra_score(company, stack_target, ["tech_stack", "technology", "tools", "stack"], "companies", str(plan.get("campaign_id", "")))
    results["tech_stack_match"] = _dimension_result(dimension="tech_stack_match", score=score, confidence=confidence, reason=reason)

    growth_fields = ["growth_signal", "hiring_signal", "employee_count", "funding_stage", "founded_year"]
    growth_value = _get_field(company, growth_fields)
    if growth_value is not None:
        score, confidence, reason = _text_match_score(growth_value, growth_target)
        if score == 0.0:
            score, confidence, reason = _numeric_bucket_score(growth_value, growth_target)
    else:
        score, confidence, reason = _semantic_extra_score(company, growth_target, ["growth", "hiring", "expansion", "funding"], "companies", str(plan.get("campaign_id", "")))
    results["growth_signal_match"] = _dimension_result(dimension="growth_signal_match", score=score, confidence=confidence, reason=reason)

    personalization_value = _get_field(company, ["description", "name", "website_url", "linkedin_url"])
    if personalization_value is not None:
        score, confidence, reason = _text_match_score(personalization_value, personalization_target)
    else:
        score, confidence, reason = _semantic_extra_score(company, personalization_target, ["personalization", "hook", "signal", "context"], "companies", str(plan.get("campaign_id", "")))
    results["personalization_signal_match"] = _dimension_result(dimension="personalization_signal_match", score=score, confidence=confidence, reason=reason)

    completeness_score, completeness_confidence, completeness_reason = _data_completeness_score(
        company,
        ["name", "domain", "industry", "employee_count", "description", "linkedin_url", "website_url"],
    )
    results["data_completeness"] = _dimension_result(
        dimension="data_completeness",
        score=completeness_score,
        confidence=completeness_confidence,
        reason=completeness_reason,
    )

    freshness_score, freshness_confidence, freshness_reason = _freshness_score(company)
    results["freshness"] = _dimension_result(
        dimension="freshness",
        score=freshness_score,
        confidence=freshness_confidence,
        reason=freshness_reason,
    )

    return results


def _person_dimension_scores(person: dict[str, Any], plan: dict[str, Any]) -> dict[str, DimensionScore]:
    poc_signals = plan.get("poc_signals") or []
    if not isinstance(poc_signals, list):
        poc_signals = []
    extra = _extra_map(person)

    title_target = _plan_signal_text(poc_signals, ["title", "role", "job_title"], "title role job title")
    seniority_target = _plan_signal_text(poc_signals, ["seniority", "level", "senior"], "seniority level senior")
    department_target = _plan_signal_text(poc_signals, ["department", "team", "function"], "department team function")
    role_target = _plan_signal_text(poc_signals, ["role", "responsibility", "title", "seniority", "department"], "role responsibility title seniority department")
    personalization_target = _plan_signal_text(poc_signals, ["personalization", "hook", "signal", "context"], "personalization signal context")

    results: dict[str, DimensionScore] = {}

    title = _get_field(person, ["title", "job_title", "role"])
    if title is not None:
        score, confidence, reason = _text_match_score(title, title_target)
    else:
        score, confidence, reason = _semantic_extra_score(person, title_target, ["title", "role", "job_title"], "persons", str(plan.get("campaign_id", "")))
    results["title_match"] = _dimension_result(dimension="title_match", score=score, confidence=confidence, reason=reason)

    seniority = _get_field(person, ["seniority", "level"])
    if seniority is not None:
        score, confidence, reason = _text_match_score(seniority, seniority_target)
    else:
        score, confidence, reason = _semantic_extra_score(person, seniority_target, ["seniority", "level", "senior"], "persons", str(plan.get("campaign_id", "")))
    results["seniority_match"] = _dimension_result(dimension="seniority_match", score=score, confidence=confidence, reason=reason)

    department = _get_field(person, ["department", "team", "function"])
    if department is not None:
        score, confidence, reason = _text_match_score(department, department_target)
    else:
        score, confidence, reason = _semantic_extra_score(person, department_target, ["department", "team", "function"], "persons", str(plan.get("campaign_id", "")))
    results["department_match"] = _dimension_result(dimension="department_match", score=score, confidence=confidence, reason=reason)

    email_verified = _get_field(person, ["email_verified"])
    score, confidence, reason = _bool_score(
        email_verified,
        True,
        "email_verified is true",
        f"email_verified is not true ({email_verified!r})",
    )
    results["email_verified"] = _dimension_result(dimension="email_verified", score=score, confidence=confidence, reason=reason)

    linkedin_url = _get_field(person, ["linkedin_url"])
    score, confidence, reason = _bool_score(
        linkedin_url,
        True,
        "linkedin_url is present",
        "linkedin_url is missing",
    )
    results["linkedin_present"] = _dimension_result(dimension="linkedin_present", score=score, confidence=confidence, reason=reason)

    role_parts = [title, seniority, department]
    role_text = " ".join(_stringify(part) for part in role_parts if part is not None)
    if role_text.strip():
        score, confidence, reason = _text_match_score(role_text, role_target)
    else:
        score, confidence, reason = _semantic_extra_score(person, role_target, ["role", "responsibility", "title", "seniority", "department"], "persons", str(plan.get("campaign_id", "")))
    results["role_relevance"] = _dimension_result(dimension="role_relevance", score=score, confidence=confidence, reason=reason)

    personalization_value = _get_field(person, ["name", "title", "linkedin_url"])
    if personalization_value is not None:
        score, confidence, reason = _text_match_score(personalization_value, personalization_target)
    else:
        score, confidence, reason = _semantic_extra_score(person, personalization_target, ["personalization", "hook", "signal", "context"], "persons", str(plan.get("campaign_id", "")))
    results["personalization_signal_match"] = _dimension_result(
        dimension="personalization_signal_match",
        score=score,
        confidence=confidence,
        reason=reason,
    )

    return results


def score_company(company: dict[str, Any], plan: dict[str, Any]) -> ScoringResult:
    weights = PlanWeights.from_plan(plan).scoring_weights
    dimension_scores = _company_dimension_scores(company, plan)
    score = _weighted_average(dimension_scores, weights)
    return ScoringResult(score=score, dimension_scores=dimension_scores)


def score_person(person: dict[str, Any], plan: dict[str, Any]) -> ScoringResult:
    weights = PlanWeights.from_plan(plan).scoring_weights
    dimension_scores = _person_dimension_scores(person, plan)
    score = _weighted_average(dimension_scores, weights)
    return ScoringResult(score=score, dimension_scores=dimension_scores)


def combined_score(company_score: float | ScoringResult, person_score: float | ScoringResult) -> float:
    company_value = company_score.score if isinstance(company_score, ScoringResult) else float(company_score)
    person_value = person_score.score if isinstance(person_score, ScoringResult) else float(person_score)
    return round(max(0.0, min(1.0, 0.65 * company_value + 0.35 * person_value)), 6)
