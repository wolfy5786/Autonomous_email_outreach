"""
Deterministic attribute→source catalog from ``data_sourcing_map.md``.

See ``docs/data-sourcing-service.md`` §5 for rule semantics.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from shared.models.enums import SourceType
from shared.models.plan import PlanRecord

# Baseline attributes always considered for sourcing (README company_record + common extras).
BASELINE_ATTRIBUTES: frozenset[str] = frozenset(
    {
        "domain",
        "name",
        "description",
        "industry",
        "employee_count",
        "headquarters",
        "funding_stage",
        "tech_stack",
        "website_url",
        "linkedin_url",
    }
)


class AttributeSourceMapRule(BaseModel):
    """
    One row of the attribute source map (see ``docs/data-sourcing-service.md`` §5).
    """

    attribute: str
    source_type: SourceType
    source_name: str
    allowed_for_discovery: bool = False
    allowed_for_enrichment: bool = True
    query_template: str | None = None
    extraction_schema: dict[str, Any] = Field(default_factory=dict)
    confidence_weight: float = 0.5
    priority: int = 10
    fallback_sources: list[str] = Field(default_factory=list)
    # Optional: vertical from data_sourcing_map (SW / HC); empty = both
    verticals: list[str] = Field(default_factory=list)


def _catalog() -> list[AttributeSourceMapRule]:
    """Build static catalog (factory to avoid mutable global)."""
    return [
        # --- Y Combinator directory ---
        AttributeSourceMapRule(
            attribute="domain",
            source_type=SourceType.DIRECTORY,
            source_name="yc_directory",
            allowed_for_discovery=True,
            allowed_for_enrichment=True,
            confidence_weight=0.95,
            priority=1,
            fallback_sources=["product_hunt", "crunchbase"],
            verticals=["SW", "HC"],
        ),
        AttributeSourceMapRule(
            attribute="name",
            source_type=SourceType.DIRECTORY,
            source_name="yc_directory",
            allowed_for_discovery=True,
            allowed_for_enrichment=True,
            confidence_weight=0.95,
            priority=1,
            fallback_sources=["product_hunt", "github_trending"],
            verticals=["SW", "HC"],
        ),
        AttributeSourceMapRule(
            attribute="description",
            source_type=SourceType.DIRECTORY,
            source_name="yc_directory",
            allowed_for_discovery=True,
            allowed_for_enrichment=True,
            confidence_weight=0.85,
            priority=2,
            fallback_sources=["company_website", "linkedin_company"],
            verticals=["SW", "HC"],
        ),
        AttributeSourceMapRule(
            attribute="yc_batch",
            source_type=SourceType.DIRECTORY,
            source_name="yc_directory",
            allowed_for_discovery=True,
            allowed_for_enrichment=True,
            confidence_weight=0.9,
            priority=2,
            verticals=["SW", "HC"],
        ),
        AttributeSourceMapRule(
            attribute="is_b2b_saas",
            source_type=SourceType.DIRECTORY,
            source_name="yc_directory",
            allowed_for_discovery=True,
            allowed_for_enrichment=True,
            confidence_weight=0.8,
            priority=3,
            verticals=["SW", "HC"],
        ),
        # --- Crunchbase (HTML / CSV; treat as scrape) ---
        AttributeSourceMapRule(
            attribute="funding_stage",
            source_type=SourceType.SCRAPE,
            source_name="crunchbase",
            allowed_for_discovery=True,
            allowed_for_enrichment=True,
            confidence_weight=0.85,
            priority=1,
            fallback_sources=["sec_edgar", "serp", "opencorporates"],
            verticals=["SW", "HC"],
        ),
        AttributeSourceMapRule(
            attribute="employee_count",
            source_type=SourceType.SCRAPE,
            source_name="crunchbase",
            allowed_for_discovery=True,
            allowed_for_enrichment=True,
            confidence_weight=0.75,
            priority=2,
            fallback_sources=["linkedin_company", "company_website"],
            verticals=["SW", "HC"],
        ),
        AttributeSourceMapRule(
            attribute="headquarters",
            source_type=SourceType.SCRAPE,
            source_name="crunchbase",
            allowed_for_discovery=True,
            allowed_for_enrichment=True,
            confidence_weight=0.8,
            priority=2,
            verticals=["SW", "HC"],
        ),
        # --- Product Hunt ---
        AttributeSourceMapRule(
            attribute="domain",
            source_type=SourceType.API,
            source_name="product_hunt",
            allowed_for_discovery=True,
            allowed_for_enrichment=True,
            confidence_weight=0.8,
            priority=2,
            fallback_sources=["yc_directory"],
            verticals=["SW"],
        ),
        AttributeSourceMapRule(
            attribute="product_hunt_launch_date",
            source_type=SourceType.API,
            source_name="product_hunt",
            allowed_for_discovery=True,
            allowed_for_enrichment=True,
            confidence_weight=0.85,
            priority=2,
            verticals=["SW"],
        ),
        AttributeSourceMapRule(
            attribute="product_hunt_upvotes",
            source_type=SourceType.API,
            source_name="product_hunt",
            allowed_for_discovery=True,
            allowed_for_enrichment=True,
            confidence_weight=0.7,
            priority=3,
            verticals=["SW"],
        ),
        # --- NIH Reporter (healthcare) ---
        AttributeSourceMapRule(
            attribute="name",
            source_type=SourceType.API,
            source_name="nih_reporter",
            allowed_for_discovery=True,
            allowed_for_enrichment=True,
            confidence_weight=0.85,
            priority=1,
            fallback_sources=["yc_directory"],
            verticals=["HC"],
        ),
        AttributeSourceMapRule(
            attribute="nih_grant_amount",
            source_type=SourceType.API,
            source_name="nih_reporter",
            allowed_for_discovery=True,
            allowed_for_enrichment=True,
            confidence_weight=0.9,
            priority=1,
            verticals=["HC"],
        ),
        AttributeSourceMapRule(
            attribute="nih_project_abstract",
            source_type=SourceType.API,
            source_name="nih_reporter",
            allowed_for_discovery=True,
            allowed_for_enrichment=True,
            confidence_weight=0.75,
            priority=2,
            verticals=["HC"],
        ),
        AttributeSourceMapRule(
            attribute="institution_name",
            source_type=SourceType.API,
            source_name="nih_reporter",
            allowed_for_discovery=True,
            allowed_for_enrichment=True,
            confidence_weight=0.85,
            priority=2,
            verticals=["HC"],
        ),
        # --- GitHub trending / orgs ---
        AttributeSourceMapRule(
            attribute="tech_stack",
            source_type=SourceType.API,
            source_name="github_trending",
            allowed_for_discovery=True,
            allowed_for_enrichment=True,
            confidence_weight=0.75,
            priority=2,
            fallback_sources=["company_website", "careers_page"],
            verticals=["SW"],
        ),
        AttributeSourceMapRule(
            attribute="github_org_url",
            source_type=SourceType.API,
            source_name="github_trending",
            allowed_for_discovery=True,
            allowed_for_enrichment=True,
            confidence_weight=0.8,
            priority=3,
            verticals=["SW"],
        ),
        # --- Hacker News (hint feed / Tier B) ---
        AttributeSourceMapRule(
            attribute="candidate_hint",
            source_type=SourceType.HINT_FEED,
            source_name="hacker_news",
            allowed_for_discovery=True,
            allowed_for_enrichment=False,
            confidence_weight=0.45,
            priority=5,
            fallback_sources=[],
            verticals=["SW"],
        ),
        # --- LinkedIn company (Tier B signal + enrichment fallback) ---
        AttributeSourceMapRule(
            attribute="industry",
            source_type=SourceType.SCRAPE,
            source_name="linkedin_company",
            allowed_for_discovery=True,
            allowed_for_enrichment=True,
            confidence_weight=0.8,
            priority=3,
            fallback_sources=["company_website"],
            verticals=["SW", "HC"],
        ),
        AttributeSourceMapRule(
            attribute="employee_count",
            source_type=SourceType.SCRAPE,
            source_name="linkedin_company",
            allowed_for_discovery=True,
            allowed_for_enrichment=True,
            confidence_weight=0.85,
            priority=3,
            verticals=["SW", "HC"],
        ),
        AttributeSourceMapRule(
            attribute="linkedin_url",
            source_type=SourceType.SCRAPE,
            source_name="linkedin_company",
            allowed_for_discovery=True,
            allowed_for_enrichment=True,
            confidence_weight=0.9,
            priority=4,
            verticals=["SW", "HC"],
        ),
        # --- Enrichment: company website + blog ---
        AttributeSourceMapRule(
            attribute="description",
            source_type=SourceType.SCRAPE,
            source_name="company_website",
            allowed_for_discovery=False,
            allowed_for_enrichment=True,
            confidence_weight=0.88,
            priority=1,
            fallback_sources=["yc_directory", "linkedin_company"],
            verticals=["SW", "HC"],
        ),
        AttributeSourceMapRule(
            attribute="icp_signals",
            source_type=SourceType.SCRAPE,
            source_name="company_website",
            allowed_for_discovery=False,
            allowed_for_enrichment=True,
            confidence_weight=0.72,
            priority=2,
            verticals=["SW", "HC"],
        ),
        AttributeSourceMapRule(
            attribute="pricing_hints",
            source_type=SourceType.SCRAPE,
            source_name="company_website",
            allowed_for_discovery=False,
            allowed_for_enrichment=True,
            confidence_weight=0.55,
            priority=3,
            verticals=["SW", "HC"],
        ),
        AttributeSourceMapRule(
            attribute="tech_stack",
            source_type=SourceType.SCRAPE,
            source_name="company_website",
            allowed_for_discovery=False,
            allowed_for_enrichment=True,
            confidence_weight=0.78,
            priority=2,
            fallback_sources=["github_trending", "careers_page"],
            verticals=["SW", "HC"],
        ),
        AttributeSourceMapRule(
            attribute="blog_recency_signal",
            source_type=SourceType.SCRAPE,
            source_name="company_website",
            allowed_for_discovery=False,
            allowed_for_enrichment=True,
            confidence_weight=0.65,
            priority=3,
            verticals=["SW", "HC"],
        ),
        # --- Careers / ATS pages ---
        AttributeSourceMapRule(
            attribute="hiring_signals",
            source_type=SourceType.SCRAPE,
            source_name="careers_page",
            allowed_for_discovery=False,
            allowed_for_enrichment=True,
            confidence_weight=0.82,
            priority=1,
            fallback_sources=["linkedin_company"],
            verticals=["SW", "HC"],
        ),
        AttributeSourceMapRule(
            attribute="open_roles_count",
            source_type=SourceType.SCRAPE,
            source_name="careers_page",
            allowed_for_discovery=False,
            allowed_for_enrichment=True,
            confidence_weight=0.8,
            priority=2,
            verticals=["SW", "HC"],
        ),
        # --- SERP (enrichment only, anchored queries) ---
        AttributeSourceMapRule(
            attribute="recent_news_summary",
            source_type=SourceType.SERP,
            source_name="serp",
            allowed_for_discovery=False,
            allowed_for_enrichment=True,
            query_template="{{company_name}} {{domain}} funding OR product launch news",
            confidence_weight=0.6,
            priority=2,
            fallback_sources=["company_website"],
            verticals=["SW", "HC"],
        ),
        AttributeSourceMapRule(
            attribute="funding_stage",
            source_type=SourceType.SERP,
            source_name="serp",
            allowed_for_discovery=False,
            allowed_for_enrichment=True,
            query_template="{{company_name}} {{domain}} funding round 2024 2025",
            confidence_weight=0.55,
            priority=3,
            fallback_sources=["sec_edgar", "crunchbase"],
            verticals=["SW", "HC"],
        ),
        # --- SEC EDGAR Form D ---
        AttributeSourceMapRule(
            attribute="sec_form_d_amount",
            source_type=SourceType.API,
            source_name="sec_edgar",
            allowed_for_discovery=False,
            allowed_for_enrichment=True,
            confidence_weight=0.92,
            priority=1,
            fallback_sources=["crunchbase", "serp"],
            verticals=["SW", "HC"],
        ),
        AttributeSourceMapRule(
            attribute="sec_form_d_filed_at",
            source_type=SourceType.API,
            source_name="sec_edgar",
            allowed_for_discovery=False,
            allowed_for_enrichment=True,
            confidence_weight=0.9,
            priority=1,
            verticals=["SW", "HC"],
        ),
        AttributeSourceMapRule(
            attribute="sec_sic_code",
            source_type=SourceType.API,
            source_name="sec_edgar",
            allowed_for_discovery=False,
            allowed_for_enrichment=True,
            confidence_weight=0.85,
            priority=2,
            verticals=["SW", "HC"],
        ),
        # --- OpenCorporates (validation / fallback) ---
        AttributeSourceMapRule(
            attribute="company_active_status",
            source_type=SourceType.API,
            source_name="opencorporates",
            allowed_for_discovery=False,
            allowed_for_enrichment=True,
            confidence_weight=0.88,
            priority=4,
            fallback_sources=[],
            verticals=["SW", "HC"],
        ),
        AttributeSourceMapRule(
            attribute="incorporation_date",
            source_type=SourceType.API,
            source_name="opencorporates",
            allowed_for_discovery=False,
            allowed_for_enrichment=True,
            confidence_weight=0.82,
            priority=4,
            verticals=["SW", "HC"],
        ),
    ]


CATALOG: list[AttributeSourceMapRule] = _catalog()


def build_source_map(plan: PlanRecord) -> list[AttributeSourceMapRule]:
    """
    Return rules from ``CATALOG`` for baseline attributes, plus one enrichment
    rule per ``outreach_context.personalization_hints`` entry.
    """
    selected: set[str] = set(BASELINE_ATTRIBUTES)

    by_key: dict[tuple[str, str], AttributeSourceMapRule] = {}
    for rule in CATALOG:
        if rule.attribute not in selected:
            continue
        key = (rule.attribute, rule.source_name)
        existing = by_key.get(key)
        if existing is None or rule.priority < existing.priority:
            by_key[key] = rule

    rules = sorted(by_key.values(), key=lambda r: (r.attribute, r.priority, r.source_name))

    # Personalization hints → enrichment via company website (crawl4ai + LLM)
    hints = (plan.outreach_context.personalization_hints if plan.outreach_context else None) or []
    hook_priority = 50
    for hint in hints:
        attr = f"hook:{hint}"
        rules.append(
            AttributeSourceMapRule(
                attribute=attr,
                source_type=SourceType.SCRAPE,
                source_name="company_website",
                allowed_for_discovery=False,
                allowed_for_enrichment=True,
                confidence_weight=0.65,
                priority=hook_priority,
                fallback_sources=["careers_page", "serp"],
                verticals=[],
            )
        )
        hook_priority += 1

    return rules
