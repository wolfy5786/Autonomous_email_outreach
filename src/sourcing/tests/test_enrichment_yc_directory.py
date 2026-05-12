"""Tests for the YC directory enrichment operation (operation 2).

Covers pure helpers (slug, __NEXT_DATA__ parse, latest-news pick) plus
orchestration via monkey-patched IO. See ``design_docs/enrichment_redesign.md``.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock

import pytest

from enrichment import yc_directory_lookup as op_module
from enrichment.base import EnrichmentContext
from enrichment.yc_directory_client import (
    YCCompany,
    YCDirectoryError,
    YCFounder,
    YCLatestNews,
    parse_yc_company_html,
    yc_slug,
)
from enrichment.yc_directory_lookup import (
    DROP_FETCH_FAILED,
    DROP_MISSING_NAME,
    DROP_NOT_IN_YC,
    DROP_NO_SIGNALS,
    YCDirectoryLookup,
)


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "name, expected",
    [
        ("Stripe", "stripe"),
        ("OpenAI", "openai"),
        ("Acme Corp", "acme-corp"),
        ("  Spaced  Name  ", "spaced-name"),
        ("Foo, Inc.", "foo-inc"),
        ("Under_score Co", "under-score-co"),
        ("", ""),
    ],
)
def test_yc_slug(name: str, expected: str) -> None:
    assert yc_slug(name) == expected


def _build_next_data_html(company_payload: dict[str, Any]) -> str:
    payload = {"props": {"pageProps": {"company": company_payload}}}
    return (
        "<html><head></head><body>"
        '<script id="__NEXT_DATA__" type="application/json">'
        f"{json.dumps(payload)}"
        "</script></body></html>"
    )


def test_parse_yc_company_html_full() -> None:
    html = _build_next_data_html(
        {
            "name": "Acme",
            "founders": [
                {"full_name": "Jane Doe", "title": "CEO"},
                {"full_name": "John Roe", "title": None},
                {"full_name": "  ", "title": "skip"},  # blank name → dropped
                "not a dict",
            ],
            "launches": [
                {
                    "title": "Acme v1",
                    "url": "https://ycombinator.com/launches/acme-v1",
                    "created_at": "2024-01-01T00:00:00Z",
                    "tagline": "first launch",
                },
                {
                    "title": "Acme v2",
                    "url": "https://ycombinator.com/launches/acme-v2",
                    "created_at": "2025-06-15T12:30:00Z",
                    "tagline": "newer launch",
                },
            ],
        }
    )
    out = parse_yc_company_html(html, profile_url="https://www.ycombinator.com/companies/acme")
    assert out is not None
    assert out.name == "Acme"
    assert out.founders == [
        YCFounder(full_name="Jane Doe", title="CEO"),
        YCFounder(full_name="John Roe", title=None),
    ]
    assert out.latest_news is not None
    # Newest launch wins regardless of list order.
    assert out.latest_news.title == "Acme v2"
    assert out.latest_news.posted_at == datetime(2025, 6, 15, 12, 30, tzinfo=timezone.utc)
    assert out.latest_news.tagline == "newer launch"


def test_parse_yc_company_html_no_next_data() -> None:
    assert parse_yc_company_html("<html>nope</html>", profile_url="x") is None


def test_parse_yc_company_html_node_missing() -> None:
    # __NEXT_DATA__ present but no company node → None.
    html = (
        '<script id="__NEXT_DATA__">{"props":{"pageProps":{"other":"x"}}}</script>'
    )
    assert parse_yc_company_html(html, profile_url="x") is None


def test_parse_yc_company_html_empty_launches() -> None:
    html = _build_next_data_html(
        {"name": "Acme", "founders": [{"full_name": "Jane Doe"}]}
    )
    out = parse_yc_company_html(html, profile_url="https://www.ycombinator.com/companies/acme")
    assert out is not None
    assert out.founders == [YCFounder(full_name="Jane Doe", title=None)]
    assert out.latest_news is None


# ---------------------------------------------------------------------------
# Orchestration (monkey-patched IO)
# ---------------------------------------------------------------------------


class _StubCompany:
    def __init__(self, name: str) -> None:
        self.name = name


class _StubPlan:
    id = "stub-plan"
    campaign_id = "stub-campaign"


def _ctx(name: str = "Acme") -> EnrichmentContext:
    return EnrichmentContext(
        campaign_id="c1",
        company=_StubCompany(name),  # type: ignore[arg-type]
        plan=_StubPlan(),  # type: ignore[arg-type]
    )


@pytest.mark.asyncio
async def test_drop_missing_company_name() -> None:
    out = await YCDirectoryLookup().run(_ctx(name=""))
    assert out.dropped is True
    assert out.drop_reason == DROP_MISSING_NAME
    assert out.attributes == {}


@pytest.mark.asyncio
async def test_drop_when_not_in_yc(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(op_module, "fetch_yc_company", AsyncMock(return_value=None))
    out = await YCDirectoryLookup().run(_ctx())
    assert out.dropped is True
    assert out.drop_reason == DROP_NOT_IN_YC


@pytest.mark.asyncio
async def test_drop_when_fetch_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        op_module,
        "fetch_yc_company",
        AsyncMock(side_effect=YCDirectoryError("503")),
    )
    out = await YCDirectoryLookup().run(_ctx())
    assert out.dropped is True
    assert out.drop_reason == DROP_FETCH_FAILED
    assert any("YCDirectoryError" in e for e in out.errors)


@pytest.mark.asyncio
async def test_drop_when_profile_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    # Profile resolved but no founders and no latest news.
    profile = YCCompany(
        profile_url="https://www.ycombinator.com/companies/acme",
        name="Acme",
        founders=[],
        latest_news=None,
    )
    monkeypatch.setattr(op_module, "fetch_yc_company", AsyncMock(return_value=profile))
    out = await YCDirectoryLookup().run(_ctx())
    assert out.dropped is True
    assert out.drop_reason == DROP_NO_SIGNALS


@pytest.mark.asyncio
async def test_happy_path_returns_provenance(monkeypatch: pytest.MonkeyPatch) -> None:
    profile_url = "https://www.ycombinator.com/companies/acme"
    profile = YCCompany(
        profile_url=profile_url,
        name="Acme",
        founders=[
            YCFounder(full_name="Jane Doe", title="CEO"),
            YCFounder(full_name="John Roe", title=None),
        ],
        latest_news=YCLatestNews(
            title="Acme v2",
            url="https://ycombinator.com/launches/acme-v2",
            posted_at=datetime(2025, 6, 15, 12, 30, tzinfo=timezone.utc),
            tagline="newer launch",
        ),
    )
    monkeypatch.setattr(op_module, "fetch_yc_company", AsyncMock(return_value=profile))

    before = datetime.now(timezone.utc)
    out = await YCDirectoryLookup().run(_ctx())

    assert out.dropped is False
    assert out.drop_reason is None
    assert out.attributes["founders"] == [
        {"full_name": "Jane Doe", "title": "CEO"},
        {"full_name": "John Roe", "title": None},
    ]
    assert out.attributes["latest_news"] == {
        "title": "Acme v2",
        "url": "https://ycombinator.com/launches/acme-v2",
        "posted_at": "2025-06-15T12:30:00+00:00",
        "tagline": "newer launch",
    }
    assert set(out.provenance.keys()) == {"founders", "latest_news"}
    for key, prov in out.provenance.items():
        assert prov.source_name == "yc_directory_lookup"
        assert prov.evidence_urls == [profile_url]
        assert prov.observed_value == out.attributes[key]
        assert prov.extracted_at >= before


# ---------------------------------------------------------------------------
# YC directory HTTP client (transport boundary, mocked)
# ---------------------------------------------------------------------------


class _FakeHttpResponse:
    def __init__(self, status_code: int, text: str = "", url: str = "") -> None:
        self.status_code = status_code
        self.text = text
        self.url = url


class _FakeHttpClient:
    """Stand-in for ``httpx.AsyncClient`` supporting only ``get``."""

    def __init__(self, response: _FakeHttpResponse) -> None:
        self._response = response
        self.last_url: str | None = None
        self.last_kwargs: dict[str, Any] | None = None

    async def get(self, url: str, **kwargs: Any) -> _FakeHttpResponse:
        self.last_url = url
        self.last_kwargs = kwargs
        return self._response


@pytest.mark.asyncio
async def test_fetch_yc_company_returns_none_on_404() -> None:
    from enrichment.yc_directory_client import fetch_yc_company

    client = _FakeHttpClient(_FakeHttpResponse(404))
    out = await fetch_yc_company("Nonexistent Co", client=client)  # type: ignore[arg-type]
    assert out is None
    assert client.last_url == "https://www.ycombinator.com/companies/nonexistent-co"
    assert client.last_kwargs is not None
    assert client.last_kwargs.get("follow_redirects") is True


@pytest.mark.asyncio
async def test_fetch_yc_company_parses_200() -> None:
    from enrichment.yc_directory_client import fetch_yc_company

    profile_url = "https://www.ycombinator.com/companies/acme"
    html = (
        '<script id="__NEXT_DATA__">'
        + json.dumps(
            {
                "props": {
                    "pageProps": {
                        "company": {
                            "name": "Acme",
                            "founders": [{"full_name": "Jane Doe", "title": "CEO"}],
                        }
                    }
                }
            }
        )
        + "</script>"
    )
    client = _FakeHttpClient(_FakeHttpResponse(200, text=html, url=profile_url))
    out = await fetch_yc_company("Acme", client=client)  # type: ignore[arg-type]
    assert out is not None
    assert out.name == "Acme"
    assert out.profile_url == profile_url
    assert out.founders == [YCFounder(full_name="Jane Doe", title="CEO")]


@pytest.mark.asyncio
async def test_fetch_yc_company_raises_on_5xx() -> None:
    from enrichment.yc_directory_client import fetch_yc_company

    client = _FakeHttpClient(_FakeHttpResponse(503))
    with pytest.raises(YCDirectoryError):
        await fetch_yc_company("Acme", client=client)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_fetch_yc_company_empty_name_returns_none() -> None:
    from enrichment.yc_directory_client import fetch_yc_company

    client = _FakeHttpClient(_FakeHttpResponse(200))
    out = await fetch_yc_company("   ", client=client)  # type: ignore[arg-type]
    assert out is None
    assert client.last_url is None  # never issued the GET
