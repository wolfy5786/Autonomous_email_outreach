from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from planning.schemas import LLMPlanOutput, LLMUsage, PlanRecord, PlanReadyEvent, PlanRequestedEvent


def test_plan_requested_event_ignores_extras() -> None:
    ev = PlanRequestedEvent.model_validate({"campaign_id": "c1", "irrelevant": "ok"})
    assert ev.campaign_id == "c1"


def test_plan_ready_event_requires_both_ids() -> None:
    with pytest.raises(ValidationError):
        PlanReadyEvent.model_validate({"campaign_id": "c1"})


def test_llm_plan_output_happy(valid_llm_output_dict: dict) -> None:
    out = LLMPlanOutput.model_validate(valid_llm_output_dict)
    assert abs(sum(out.scoring_weights.values()) - 1.0) < 0.05


def test_llm_plan_output_weights_must_sum_to_one(valid_llm_output_dict: dict) -> None:
    bad = dict(valid_llm_output_dict)
    bad["scoring_weights"] = {"industry_match": 0.2, "size_match": 0.2}  # sums to 0.4
    with pytest.raises(ValidationError):
        LLMPlanOutput.model_validate(bad)


def test_llm_plan_output_rejects_negative_weights(valid_llm_output_dict: dict) -> None:
    bad = dict(valid_llm_output_dict)
    bad["scoring_weights"] = {"a": 1.2, "b": -0.2}  # sums to 1.0 but has negative
    with pytest.raises(ValidationError):
        LLMPlanOutput.model_validate(bad)


def test_llm_plan_output_email_tone_is_restricted(valid_llm_output_dict: dict) -> None:
    bad = dict(valid_llm_output_dict)
    bad["email_tone"] = "flirty"
    with pytest.raises(ValidationError):
        LLMPlanOutput.model_validate(bad)


def test_llm_plan_output_requires_min_signals(valid_llm_output_dict: dict) -> None:
    bad = dict(valid_llm_output_dict)
    bad["company_signals"] = ["only one"]
    with pytest.raises(ValidationError):
        LLMPlanOutput.model_validate(bad)


def test_plan_record_requires_meta(valid_llm_output_dict: dict) -> None:
    record = PlanRecord(
        id=uuid4(),
        campaign_id="c1",
        created_at=datetime.now(timezone.utc),
        llm_model="gemini/gemini-1.5-pro",
        llm_usage=LLMUsage(prompt_tokens=100, completion_tokens=200, total_tokens=300),
        **valid_llm_output_dict,
    )
    assert record.campaign_id == "c1"
    assert record.llm_usage.total_tokens == 300


def test_llm_plan_output_extra_fields_rejected(valid_llm_output_dict: dict) -> None:
    bad = dict(valid_llm_output_dict)
    bad["unexpected"] = "oops"
    with pytest.raises(ValidationError):
        LLMPlanOutput.model_validate(bad)
