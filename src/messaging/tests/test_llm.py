import json
from unittest.mock import AsyncMock, MagicMock

import litellm
import pytest
from pydantic import ValidationError

import messaging.llm as llm_mod
from messaging.llm import LLMGenerationError, generate_draft
from messaging.schemas import CompanyContext, HintContext, PlanContext, PocRecord


def _inputs():
    return dict(
        plan=PlanContext(
            id="pl1", campaign_id="c1", email_tone="warm",
            email_angle="cut incident response time",
        ),
        company=CompanyContext(id="co1", name="Acme", domain="acme.com"),
        poc=PocRecord(id="p1", company_id="co1", email="sam@acme.com", first_name="Sam"),
        hints=[HintContext(category="funding", summary="Raised $20M Series B")],
    )


def _mock_response(content: str, prompt_tokens: int = 10, completion_tokens: int = 20):
    """Build a fake litellm.acompletion response."""
    msg = MagicMock(content=content)
    choice = MagicMock(message=msg)
    usage = MagicMock()
    usage.model_dump.return_value = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
    }
    resp = MagicMock(choices=[choice], usage=usage)
    return resp


_VALID_JSON = json.dumps(
    {
        "subject": "Quick thought on your platform team",
        "body": "Hi Sam — saw the Series B last month. " * 5,
        "personalization_hooks": ["funding"],
    }
)


class TestGenerateDraftHappyPath:
    async def test_returns_parsed_output_and_usage(self, mocker):
        mocker.patch.object(
            llm_mod.litellm, "acompletion",
            new=AsyncMock(return_value=_mock_response(_VALID_JSON)),
        )
        out, usage = await generate_draft(**_inputs())
        assert out.subject.startswith("Quick")
        assert usage.total_tokens == 30


class TestRepairLoop:
    async def test_recovers_after_one_invalid_response(self, mocker):
        # First call returns invalid (body too short), second returns valid.
        bad = json.dumps({"subject": "hi there", "body": "tiny", "personalization_hooks": ["x"]})
        ac = AsyncMock(side_effect=[_mock_response(bad), _mock_response(_VALID_JSON)])
        mocker.patch.object(llm_mod.litellm, "acompletion", new=ac)

        out, _ = await generate_draft(**_inputs())
        assert out.subject.startswith("Quick")
        assert ac.await_count == 2

        # Second call should include the assistant message with the bad output (repair prompt).
        second_messages = ac.await_args_list[1].kwargs["messages"]
        assert any(m["role"] == "assistant" and m["content"] == bad for m in second_messages)

    async def test_raises_when_all_attempts_fail_validation(self, mocker, monkeypatch):
        monkeypatch.setattr(llm_mod.settings, "llm_max_retries", 2)
        bad = json.dumps({"subject": "hi", "body": "x", "personalization_hooks": []})
        mocker.patch.object(
            llm_mod.litellm, "acompletion",
            new=AsyncMock(return_value=_mock_response(bad)),
        )
        with pytest.raises((LLMGenerationError, ValidationError)):
            await generate_draft(**_inputs())


class TestTransientErrors:
    async def test_retries_rate_limit_then_succeeds(self, mocker):
        ac = AsyncMock(
            side_effect=[
                litellm.RateLimitError("slow down", model="x", llm_provider="y"),
                _mock_response(_VALID_JSON),
            ]
        )
        mocker.patch.object(llm_mod.litellm, "acompletion", new=ac)
        out, _ = await generate_draft(**_inputs())
        assert out.subject.startswith("Quick")
        assert ac.await_count == 2


class TestPromptAssembly:
    async def test_first_call_includes_all_context(self, mocker):
        ac = AsyncMock(return_value=_mock_response(_VALID_JSON))
        mocker.patch.object(llm_mod.litellm, "acompletion", new=ac)
        await generate_draft(**_inputs())
        msgs = ac.await_args.kwargs["messages"]
        assert msgs[0]["role"] == "system"
        assert "STAY GROUNDED" in msgs[0]["content"] or "Use ONLY facts" in msgs[0]["content"]
        user = msgs[1]["content"]
        assert "sam@acme.com" in user
        assert "acme.com" in user
        assert "warm" in user
        assert "Series B" in user
