import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from planning import llm as llm_module
from planning.llm import LLMGenerationError, generate_plan


def _fake_response(content: str, usage: dict[str, int] | None = None) -> MagicMock:
    resp = MagicMock()
    message = MagicMock()
    message.content = content
    choice = MagicMock()
    choice.message = message
    resp.choices = [choice]
    if usage is not None:
        usage_obj = MagicMock()
        usage_obj.model_dump.return_value = usage
        resp.usage = usage_obj
    else:
        resp.usage = None
    return resp


async def test_generate_plan_happy_path(
    monkeypatch: pytest.MonkeyPatch, valid_llm_output_dict: dict[str, Any], sample_icp, sample_product
) -> None:
    mock = AsyncMock(
        return_value=_fake_response(
            json.dumps(valid_llm_output_dict),
            {"prompt_tokens": 100, "completion_tokens": 200, "total_tokens": 300},
        )
    )
    monkeypatch.setattr(llm_module.litellm, "acompletion", mock)

    parsed, usage = await generate_plan(sample_icp, sample_product)

    assert parsed.email_tone == "technical"
    assert usage.total_tokens == 300
    assert mock.await_count == 1
    # The model string is passed through from settings.
    kwargs = mock.await_args.kwargs
    assert kwargs["model"] == llm_module.settings.llm_model
    assert kwargs["response_format"]["type"] == "json_schema"


async def test_generate_plan_retries_on_invalid_json(
    monkeypatch: pytest.MonkeyPatch, valid_llm_output_dict: dict[str, Any], sample_icp, sample_product
) -> None:
    # First call returns invalid (empty weights sum != 1), second returns valid.
    bad = dict(valid_llm_output_dict)
    bad["scoring_weights"] = {"industry_match": 0.1}
    sequence = [
        _fake_response(json.dumps(bad)),
        _fake_response(json.dumps(valid_llm_output_dict)),
    ]

    async def fake_acompletion(**_: Any) -> Any:
        return sequence.pop(0)

    monkeypatch.setattr(llm_module.litellm, "acompletion", fake_acompletion)
    # Avoid slow backoff in the test.
    monkeypatch.setattr(llm_module.settings, "llm_max_retries", 3)

    parsed, _ = await generate_plan(sample_icp, sample_product)
    assert parsed.email_tone == valid_llm_output_dict["email_tone"]


async def test_generate_plan_exhausts_retries_on_persistent_bad_output(
    monkeypatch: pytest.MonkeyPatch, valid_llm_output_dict: dict[str, Any], sample_icp, sample_product
) -> None:
    bad = dict(valid_llm_output_dict)
    bad["scoring_weights"] = {"industry_match": 0.1}  # never sums to 1

    async def fake_acompletion(**_: Any) -> Any:
        return _fake_response(json.dumps(bad))

    monkeypatch.setattr(llm_module.litellm, "acompletion", fake_acompletion)
    monkeypatch.setattr(llm_module.settings, "llm_max_retries", 2)

    with pytest.raises((LLMGenerationError, Exception)):
        await generate_plan(sample_icp, sample_product)


async def test_generate_plan_retries_on_rate_limit(
    monkeypatch: pytest.MonkeyPatch, valid_llm_output_dict: dict[str, Any], sample_icp, sample_product
) -> None:
    calls = {"n": 0}

    async def fake_acompletion(**_: Any) -> Any:
        calls["n"] += 1
        if calls["n"] == 1:
            raise llm_module.litellm.RateLimitError(
                "rate limit", model=llm_module.settings.llm_model, llm_provider="gemini"
            )
        return _fake_response(json.dumps(valid_llm_output_dict))

    monkeypatch.setattr(llm_module.litellm, "acompletion", fake_acompletion)
    monkeypatch.setattr(llm_module.settings, "llm_max_retries", 3)

    parsed, _ = await generate_plan(sample_icp, sample_product)
    assert parsed.email_tone == "technical"
    assert calls["n"] == 2
