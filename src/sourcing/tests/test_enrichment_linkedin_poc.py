"""Tests for the LinkedIn POC enrichment operation (operation 1).

Covers pure helpers (SERP URL filter, login-wall detection, LLM JSON parsing)
plus orchestration via monkey-patched IO. See ``design_docs/enrichment_redesign.md``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock

import pytest

from enrichment import linkedin_poc as op_module
from enrichment.base import EnrichmentContext
from enrichment.crawl import PageFetchResult, _is_login_wall
from enrichment.linkedin_poc import (
    DROP_LLM_FAILED,
    DROP_LOGIN_REQUIRED,
    DROP_MISSING_NAME,
    DROP_NO_LINKEDIN_URL,
    DROP_NO_POC_VISIBLE,
    DROP_SERP_FAILED,
    DROP_SERP_NOT_CONFIGURED,
    LinkedInPocLookup,
)
from enrichment.llm import LinkedInPocExtraction, LLMExtractionError, _parse_poc
from enrichment.serp_client import SerpAPIError, SerpHit, _is_linkedin_url


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://www.linkedin.com/company/acme", True),
        ("https://linkedin.com/in/jane-doe", True),
        ("https://uk.linkedin.com/company/acme-uk", True),
        ("https://news.ycombinator.com/item?id=1", False),
        ("https://linkedin.io/spoof", False),
        ("https://example.com/about", False),
        ("not a url", False),
        ("", False),
    ],
)
def test_is_linkedin_url(url: str, expected: bool) -> None:
    assert _is_linkedin_url(url) is expected


@pytest.mark.parametrize(
    "final_url, markdown, expected",
    [
        ("https://www.linkedin.com/authwall?...", "anything", True),
        ("https://www.linkedin.com/login", "anything", True),
        ("https://www.linkedin.com/uas/login", "anything", True),
        ("https://www.linkedin.com/checkpoint/lg/login", "anything", True),
        (
            "https://www.linkedin.com/company/acme",
            "Sign in\nJoin now",
            True,  # thin body + both CTAs → wall
        ),
        (
            "https://www.linkedin.com/company/acme",
            "Acme is a long page with About, Posts, Employees, and so on " * 50,
            False,
        ),
    ],
)
def test_is_login_wall(final_url: str, markdown: str, expected: bool) -> None:
    assert _is_login_wall(final_url, markdown) is expected


def test_parse_poc_plain_json() -> None:
    raw = (
        '{"poc_name": "Jane Doe", "poc_title": "CEO",'
        ' "poc_profile_url": "https://linkedin.com/in/jane", "rationale": "founder"}'
    )
    out = _parse_poc(raw)
    assert out.poc_name == "Jane Doe"
    assert out.poc_title == "CEO"
    assert out.poc_profile_url == "https://linkedin.com/in/jane"


def test_parse_poc_code_fence_wrapped() -> None:
    raw = '```json\n{"poc_name": "Jane Doe", "poc_title": null, "poc_profile_url": null, "rationale": null}\n```'
    out = _parse_poc(raw)
    assert out.poc_name == "Jane Doe"
    assert out.poc_title is None


def test_parse_poc_invalid_raises() -> None:
    with pytest.raises(LLMExtractionError):
        _parse_poc("not json at all")


# ---------------------------------------------------------------------------
# Orchestration (monkey-patched IO)
# ---------------------------------------------------------------------------


class _StubCompany:
    def __init__(self, name: str) -> None:
        self.name = name


class _StubPlan:
    id = "stub-plan"
    campaign_id = "stub-campaign"


def _ctx(name: str = "Acme Corp") -> EnrichmentContext:
    """EnrichmentContext using lightweight stand-ins.

    CompanyRecord / PlanRecord are Beanie documents that require a Mongo
    connection on instantiation; for these tests we only need ``.name``.
    """
    return EnrichmentContext(
        campaign_id="c1",
        company=_StubCompany(name),  # type: ignore[arg-type]
        plan=_StubPlan(),  # type: ignore[arg-type]
    )


@pytest.mark.asyncio
async def test_drop_missing_company_name() -> None:
    ctx = _ctx(name="")
    out = await LinkedInPocLookup().run(ctx)
    assert out.dropped is True
    assert out.drop_reason == DROP_MISSING_NAME
    assert out.attributes == {}


@pytest.mark.asyncio
async def test_drop_when_serp_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(op_module.settings, "serpapi_api_key", None)
    out = await LinkedInPocLookup().run(_ctx())
    assert out.dropped is True
    assert out.drop_reason == DROP_SERP_NOT_CONFIGURED
    assert any("SERPAPI_API_KEY" in e for e in out.errors)


@pytest.mark.asyncio
async def test_drop_when_serp_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(op_module.settings, "serpapi_api_key", "k")
    monkeypatch.setattr(
        op_module,
        "find_company_linkedin_url",
        AsyncMock(side_effect=SerpAPIError("503")),
    )
    out = await LinkedInPocLookup().run(_ctx())
    assert out.dropped is True
    assert out.drop_reason == DROP_SERP_FAILED


@pytest.mark.asyncio
async def test_drop_when_no_linkedin_in_serp(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(op_module.settings, "serpapi_api_key", "k")
    monkeypatch.setattr(
        op_module,
        "find_company_linkedin_url",
        AsyncMock(return_value=None),
    )
    out = await LinkedInPocLookup().run(_ctx())
    assert out.dropped is True
    assert out.drop_reason == DROP_NO_LINKEDIN_URL


@pytest.mark.asyncio
async def test_drop_on_login_wall(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(op_module.settings, "serpapi_api_key", "k")
    hit = SerpHit(url="https://www.linkedin.com/company/acme", title=None, snippet=None)
    monkeypatch.setattr(
        op_module, "find_company_linkedin_url", AsyncMock(return_value=hit)
    )
    page = PageFetchResult(
        requested_url=hit.url,
        final_url="https://www.linkedin.com/authwall?session=1",
        markdown="Sign in",
        login_wall=True,
    )
    monkeypatch.setattr(op_module, "fetch_single_page", AsyncMock(return_value=page))

    out = await LinkedInPocLookup().run(_ctx())
    assert out.dropped is True
    assert out.drop_reason == DROP_LOGIN_REQUIRED


@pytest.mark.asyncio
async def test_drop_on_llm_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(op_module.settings, "serpapi_api_key", "k")
    hit = SerpHit(url="https://www.linkedin.com/company/acme", title=None, snippet=None)
    page = PageFetchResult(
        requested_url=hit.url,
        final_url=hit.url,
        markdown="About Acme — we do widgets.",
        login_wall=False,
    )
    monkeypatch.setattr(
        op_module, "find_company_linkedin_url", AsyncMock(return_value=hit)
    )
    monkeypatch.setattr(op_module, "fetch_single_page", AsyncMock(return_value=page))
    monkeypatch.setattr(
        op_module,
        "extract_linkedin_poc",
        AsyncMock(side_effect=LLMExtractionError("bad json")),
    )

    out = await LinkedInPocLookup().run(_ctx())
    assert out.dropped is True
    assert out.drop_reason == DROP_LLM_FAILED


@pytest.mark.asyncio
async def test_drop_when_llm_returns_no_poc(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(op_module.settings, "serpapi_api_key", "k")
    hit = SerpHit(url="https://www.linkedin.com/company/acme", title=None, snippet=None)
    page = PageFetchResult(
        requested_url=hit.url,
        final_url=hit.url,
        markdown="About Acme — we do widgets.",
        login_wall=False,
    )
    monkeypatch.setattr(
        op_module, "find_company_linkedin_url", AsyncMock(return_value=hit)
    )
    monkeypatch.setattr(op_module, "fetch_single_page", AsyncMock(return_value=page))
    monkeypatch.setattr(
        op_module,
        "extract_linkedin_poc",
        AsyncMock(return_value=LinkedInPocExtraction()),
    )

    out = await LinkedInPocLookup().run(_ctx())
    assert out.dropped is True
    assert out.drop_reason == DROP_NO_POC_VISIBLE


@pytest.mark.asyncio
async def test_happy_path_returns_provenance(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(op_module.settings, "serpapi_api_key", "k")
    hit = SerpHit(url="https://www.linkedin.com/company/acme", title="Acme", snippet=None)
    page = PageFetchResult(
        requested_url=hit.url,
        final_url=hit.url,
        markdown="About Acme — CEO Jane Doe.",
        login_wall=False,
    )
    poc = LinkedInPocExtraction(
        poc_name="Jane Doe",
        poc_title="CEO",
        poc_profile_url="https://www.linkedin.com/in/jane-doe",
        rationale="listed as CEO on the company About",
    )
    monkeypatch.setattr(
        op_module, "find_company_linkedin_url", AsyncMock(return_value=hit)
    )
    monkeypatch.setattr(op_module, "fetch_single_page", AsyncMock(return_value=page))
    monkeypatch.setattr(
        op_module, "extract_linkedin_poc", AsyncMock(return_value=poc)
    )

    before = datetime.now(timezone.utc)
    out = await LinkedInPocLookup().run(_ctx())

    assert out.dropped is False
    assert out.drop_reason is None
    assert out.attributes == {
        "poc_name": "Jane Doe",
        "evidence_url": hit.url,
        "poc_title": "CEO",
        "poc_profile_url": "https://www.linkedin.com/in/jane-doe",
    }
    assert set(out.provenance.keys()) == set(out.attributes.keys())
    for key, prov in out.provenance.items():
        assert prov.source_name == "linkedin_poc"
        assert prov.evidence_urls == [hit.url]
        assert prov.observed_value == out.attributes[key]
        assert prov.extracted_at >= before


# ---------------------------------------------------------------------------
# SerpAPI client (HTTP boundary, mocked transport)
# ---------------------------------------------------------------------------


class _FakeHttpResponse:
    def __init__(self, status_code: int, payload: Any) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> Any:
        return self._payload


class _FakeHttpClient:
    """Stand-in for httpx.AsyncClient supporting only ``get``."""

    def __init__(self, response: _FakeHttpResponse) -> None:
        self._response = response
        self.last_params: dict[str, Any] | None = None

    async def get(self, url: str, params: dict[str, Any], timeout: float) -> _FakeHttpResponse:
        self.last_params = params
        return self._response


@pytest.mark.asyncio
async def test_find_company_linkedin_url_picks_first_linkedin_hit() -> None:
    from enrichment.serp_client import find_company_linkedin_url

    payload = {
        "organic_results": [
            {"link": "https://news.ycombinator.com/item", "title": "HN"},
            {"link": "https://www.linkedin.com/company/acme", "title": "Acme | LinkedIn"},
            {"link": "https://www.linkedin.com/company/acme-uk", "title": "Acme UK"},
        ]
    }
    client = _FakeHttpClient(_FakeHttpResponse(200, payload))

    hit = await find_company_linkedin_url("Acme Corp", api_key="k", client=client)  # type: ignore[arg-type]

    assert hit is not None
    assert hit.url == "https://www.linkedin.com/company/acme"
    assert client.last_params is not None
    assert client.last_params["q"] == '"Acme Corp" LinkedIn'
    assert client.last_params["engine"] == "google"


@pytest.mark.asyncio
async def test_find_company_linkedin_url_returns_none_when_no_match() -> None:
    from enrichment.serp_client import find_company_linkedin_url

    payload = {
        "organic_results": [
            {"link": "https://news.ycombinator.com/item"},
            {"link": "https://example.com"},
        ]
    }
    client = _FakeHttpClient(_FakeHttpResponse(200, payload))
    hit = await find_company_linkedin_url("Acme Corp", api_key="k", client=client)  # type: ignore[arg-type]
    assert hit is None


@pytest.mark.asyncio
async def test_find_company_linkedin_url_raises_on_non_200() -> None:
    from enrichment.serp_client import find_company_linkedin_url

    client = _FakeHttpClient(_FakeHttpResponse(503, {}))
    with pytest.raises(SerpAPIError):
        await find_company_linkedin_url("Acme Corp", api_key="k", client=client)  # type: ignore[arg-type]
