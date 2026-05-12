"""Tests for the company website enrichment operation (operation 3).

Covers pure helpers (generic login-wall detection, non-canonical host filter,
LLM JSON parsing, seed URL resolution) plus orchestration via monkey-patched
IO. See ``design_docs/enrichment_redesign.md`` §3.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock

import pytest

from enrichment import company_website as op_module
from enrichment.base import EnrichmentContext
from enrichment.company_website import (
    DROP_CRAWL_FAILED,
    DROP_EMPTY_EXTRACTION,
    DROP_LLM_FAILED,
    DROP_LOGIN_REQUIRED,
    DROP_MISSING_NAME,
    DROP_NO_URL_RESOLVED,
    DROP_SERP_FAILED,
    DROP_SERP_NOT_CONFIGURED,
    CompanyWebsiteExtraction,
    _seed_url_from_company,
)
from enrichment.crawl import PageFetchResult, _is_login_wall
from enrichment.llm import (
    CompanyWebsiteInfo,
    LLMExtractionError,
    _parse_company_website,
)
from enrichment.serp_client import SerpAPIError, SerpHit, _is_non_canonical_host


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "final_url, markdown, expected",
    [
        # Generic /login redirect → wall.
        ("https://acme.com/login", "anything", True),
        ("https://acme.com/auth/signin", "anything", True),
        ("https://acme.com/sso", "anything", True),
        # Thin paywall body.
        (
            "https://news.example.com/article",
            "Please sign in to continue reading our content.",
            True,
        ),
        # Age gate.
        (
            "https://example.com/",
            "Verify your age before entering this site.",
            True,
        ),
        # Healthy landing page is not a wall.
        (
            "https://acme.com/",
            "Acme — the leading widget platform. " * 100,
            False,
        ),
    ],
)
def test_is_login_wall_generic(final_url: str, markdown: str, expected: bool) -> None:
    assert _is_login_wall(final_url, markdown) is expected


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://acme.com/", False),
        ("https://www.acme.com/about", False),
        ("https://www.linkedin.com/company/acme", True),
        ("https://crunchbase.com/organization/acme", True),
        ("https://en.wikipedia.org/wiki/Acme", True),
        ("https://www.ycombinator.com/companies/acme", True),
        ("not a url", True),  # unparseable hostname → treat as non-canonical
    ],
)
def test_is_non_canonical_host(url: str, expected: bool) -> None:
    assert _is_non_canonical_host(url) is expected


def test_parse_company_website_plain_json() -> None:
    raw = (
        '{"company_summary": "Acme builds widgets.",'
        ' "value_props": ["fast", "secure"],'
        ' "target_market": "B2B SaaS",'
        ' "signals": ["Series A", "1000+ customers"]}'
    )
    out = _parse_company_website(raw)
    assert out.company_summary == "Acme builds widgets."
    assert out.value_props == ["fast", "secure"]
    assert out.target_market == "B2B SaaS"
    assert out.signals == ["Series A", "1000+ customers"]


def test_parse_company_website_code_fence_wrapped() -> None:
    raw = (
        "```json\n"
        '{"company_summary": "Acme builds widgets.", "value_props": [],'
        ' "target_market": null, "signals": []}\n'
        "```"
    )
    out = _parse_company_website(raw)
    assert out.company_summary == "Acme builds widgets."
    assert out.value_props == []
    assert out.target_market is None


def test_parse_company_website_invalid_raises() -> None:
    with pytest.raises(LLMExtractionError):
        _parse_company_website("not json at all")


class _Co:
    def __init__(self, *, name: str = "Acme", website_url: str | None = None, domain: str | None = None) -> None:
        self.name = name
        self.website_url = website_url
        self.domain = domain


@pytest.mark.parametrize(
    "website_url, domain, expected",
    [
        ("https://acme.com", None, "https://acme.com"),
        ("http://acme.com/", None, "http://acme.com/"),
        ("acme.com", None, "https://acme.com"),  # bare host → promote to https
        (None, "acme.com", "https://acme.com"),
        ("   ", "acme.com", "https://acme.com"),
        (None, None, None),
        ("", "", None),
    ],
)
def test_seed_url_from_company(website_url: str | None, domain: str | None, expected: str | None) -> None:
    co = _Co(website_url=website_url, domain=domain)
    assert _seed_url_from_company(co) == expected


# ---------------------------------------------------------------------------
# Orchestration (monkey-patched IO)
# ---------------------------------------------------------------------------


class _StubPlan:
    id = "stub-plan"
    campaign_id = "stub-campaign"


def _ctx(
    *,
    name: str = "Acme Corp",
    website_url: str | None = None,
    domain: str | None = None,
) -> EnrichmentContext:
    return EnrichmentContext(
        campaign_id="c1",
        company=_Co(name=name, website_url=website_url, domain=domain),  # type: ignore[arg-type]
        plan=_StubPlan(),  # type: ignore[arg-type]
    )


@pytest.mark.asyncio
async def test_drop_missing_company_name() -> None:
    out = await CompanyWebsiteExtraction().run(_ctx(name=""))
    assert out.dropped is True
    assert out.drop_reason == DROP_MISSING_NAME
    assert out.attributes == {}


@pytest.mark.asyncio
async def test_drop_when_serp_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    # No website_url / domain on the company → SERP fallback is required.
    monkeypatch.setattr(op_module.settings, "serpapi_api_key", None)
    out = await CompanyWebsiteExtraction().run(_ctx())
    assert out.dropped is True
    assert out.drop_reason == DROP_SERP_NOT_CONFIGURED
    assert any("SERPAPI_API_KEY" in e for e in out.errors)


@pytest.mark.asyncio
async def test_drop_when_serp_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(op_module.settings, "serpapi_api_key", "k")
    monkeypatch.setattr(
        op_module,
        "find_company_website_url",
        AsyncMock(side_effect=SerpAPIError("503")),
    )
    out = await CompanyWebsiteExtraction().run(_ctx())
    assert out.dropped is True
    assert out.drop_reason == DROP_SERP_FAILED


@pytest.mark.asyncio
async def test_drop_when_no_url_resolved(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(op_module.settings, "serpapi_api_key", "k")
    monkeypatch.setattr(
        op_module, "find_company_website_url", AsyncMock(return_value=None)
    )
    out = await CompanyWebsiteExtraction().run(_ctx())
    assert out.dropped is True
    assert out.drop_reason == DROP_NO_URL_RESOLVED


@pytest.mark.asyncio
async def test_skips_serp_when_website_url_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the company already has a URL, op 3 must not call SERP."""
    monkeypatch.setattr(op_module.settings, "serpapi_api_key", None)  # would fail SERP
    serp_mock = AsyncMock(return_value=None)
    monkeypatch.setattr(op_module, "find_company_website_url", serp_mock)

    page = PageFetchResult(
        requested_url="https://acme.com",
        final_url="https://acme.com",
        markdown="Acme builds widgets for everyone.",
        login_wall=False,
    )
    monkeypatch.setattr(op_module, "fetch_single_page", AsyncMock(return_value=page))
    monkeypatch.setattr(
        op_module,
        "extract_company_website_info",
        AsyncMock(
            return_value=CompanyWebsiteInfo(
                company_summary="Acme builds widgets.",
                value_props=["fast"],
                target_market=None,
                signals=[],
            )
        ),
    )

    out = await CompanyWebsiteExtraction().run(_ctx(website_url="https://acme.com"))

    serp_mock.assert_not_called()
    assert out.dropped is False
    assert out.attributes["company_summary"] == "Acme builds widgets."


@pytest.mark.asyncio
async def test_drop_on_crawl_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    from enrichment.crawl import CrawlError

    monkeypatch.setattr(
        op_module,
        "fetch_single_page",
        AsyncMock(side_effect=CrawlError("boom")),
    )
    out = await CompanyWebsiteExtraction().run(_ctx(website_url="https://acme.com"))
    assert out.dropped is True
    assert out.drop_reason == DROP_CRAWL_FAILED


@pytest.mark.asyncio
async def test_drop_on_login_wall(monkeypatch: pytest.MonkeyPatch) -> None:
    page = PageFetchResult(
        requested_url="https://acme.com",
        final_url="https://acme.com/login",
        markdown="Please sign in.",
        login_wall=True,
    )
    monkeypatch.setattr(op_module, "fetch_single_page", AsyncMock(return_value=page))
    out = await CompanyWebsiteExtraction().run(_ctx(website_url="https://acme.com"))
    assert out.dropped is True
    assert out.drop_reason == DROP_LOGIN_REQUIRED


@pytest.mark.asyncio
async def test_drop_on_llm_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    page = PageFetchResult(
        requested_url="https://acme.com",
        final_url="https://acme.com",
        markdown="Acme is a widget company.",
        login_wall=False,
    )
    monkeypatch.setattr(op_module, "fetch_single_page", AsyncMock(return_value=page))
    monkeypatch.setattr(
        op_module,
        "extract_company_website_info",
        AsyncMock(side_effect=LLMExtractionError("bad json")),
    )
    out = await CompanyWebsiteExtraction().run(_ctx(website_url="https://acme.com"))
    assert out.dropped is True
    assert out.drop_reason == DROP_LLM_FAILED


@pytest.mark.asyncio
async def test_drop_when_extraction_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    page = PageFetchResult(
        requested_url="https://acme.com",
        final_url="https://acme.com",
        markdown="Acme",
        login_wall=False,
    )
    monkeypatch.setattr(op_module, "fetch_single_page", AsyncMock(return_value=page))
    monkeypatch.setattr(
        op_module,
        "extract_company_website_info",
        AsyncMock(return_value=CompanyWebsiteInfo()),  # all fields empty
    )
    out = await CompanyWebsiteExtraction().run(_ctx(website_url="https://acme.com"))
    assert out.dropped is True
    assert out.drop_reason == DROP_EMPTY_EXTRACTION


@pytest.mark.asyncio
async def test_happy_path_via_serp(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(op_module.settings, "serpapi_api_key", "k")
    hit = SerpHit(url="https://acme.com", title="Acme", snippet=None)
    page = PageFetchResult(
        requested_url=hit.url,
        final_url=hit.url,
        markdown="Acme builds widgets. Backed by ABC Ventures.",
        login_wall=False,
    )
    info = CompanyWebsiteInfo(
        company_summary="Acme builds widgets.",
        value_props=["fast", "secure"],
        target_market="B2B SaaS",
        signals=["Backed by ABC Ventures"],
    )
    monkeypatch.setattr(
        op_module, "find_company_website_url", AsyncMock(return_value=hit)
    )
    monkeypatch.setattr(op_module, "fetch_single_page", AsyncMock(return_value=page))
    monkeypatch.setattr(
        op_module,
        "extract_company_website_info",
        AsyncMock(return_value=info),
    )

    before = datetime.now(timezone.utc)
    out = await CompanyWebsiteExtraction().run(_ctx())

    assert out.dropped is False
    assert out.drop_reason is None
    assert out.attributes == {
        "company_summary": "Acme builds widgets.",
        "value_props": ["fast", "secure"],
        "target_market": "B2B SaaS",
        "signals": ["Backed by ABC Ventures"],
        "source_url": hit.url,
    }
    assert set(out.provenance.keys()) == set(out.attributes.keys())
    for key, prov in out.provenance.items():
        assert prov.source_name == "company_website"
        assert prov.evidence_urls == [hit.url]
        assert prov.observed_value == out.attributes[key]
        assert prov.extracted_at >= before


# ---------------------------------------------------------------------------
# SerpAPI client — top-result lookup (transport boundary, mocked)
# ---------------------------------------------------------------------------


class _FakeHttpResponse:
    def __init__(self, status_code: int, payload: Any) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> Any:
        return self._payload


class _FakeHttpClient:
    def __init__(self, response: _FakeHttpResponse) -> None:
        self._response = response
        self.last_params: dict[str, Any] | None = None

    async def get(self, url: str, params: dict[str, Any], timeout: float) -> _FakeHttpResponse:
        self.last_params = params
        return self._response


@pytest.mark.asyncio
async def test_find_company_website_url_skips_aggregators() -> None:
    from enrichment.serp_client import find_company_website_url

    payload = {
        "organic_results": [
            {"link": "https://www.linkedin.com/company/acme"},
            {"link": "https://en.wikipedia.org/wiki/Acme"},
            {"link": "https://acme.com", "title": "Acme"},
            {"link": "https://other.example.com"},
        ]
    }
    client = _FakeHttpClient(_FakeHttpResponse(200, payload))

    hit = await find_company_website_url("Acme Corp", api_key="k", client=client)  # type: ignore[arg-type]

    assert hit is not None
    assert hit.url == "https://acme.com"
    assert client.last_params is not None
    assert client.last_params["q"] == "Acme Corp"


@pytest.mark.asyncio
async def test_find_company_website_url_returns_none_when_all_aggregators() -> None:
    from enrichment.serp_client import find_company_website_url

    payload = {
        "organic_results": [
            {"link": "https://www.linkedin.com/company/acme"},
            {"link": "https://crunchbase.com/organization/acme"},
        ]
    }
    client = _FakeHttpClient(_FakeHttpResponse(200, payload))
    hit = await find_company_website_url("Acme Corp", api_key="k", client=client)  # type: ignore[arg-type]
    assert hit is None
