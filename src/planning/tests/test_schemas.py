from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from planning.schemas import (
    EmployeeCountRange,
    GlobalFilters,
    LLMPlanOutput,
    LLMUsage,
    OutreachContext,
    PlanReadyEvent,
    PlanRecord,
    PlanRequestedEvent,
    ProductHuntSource,
    SourcingRequestedEvent,
    YCNewsSource,
)


# --- Events ---

def test_plan_requested_event_ignores_extras() -> None:
    ev = PlanRequestedEvent.model_validate({"campaign_id": "c1", "irrelevant": "ok"})
    assert ev.campaign_id == "c1"


def test_plan_ready_event_requires_both_ids() -> None:
    with pytest.raises(ValidationError):
        PlanReadyEvent.model_validate({"campaign_id": "c1"})


def test_sourcing_requested_event_requires_both_ids() -> None:
    with pytest.raises(ValidationError):
        SourcingRequestedEvent.model_validate({"campaign_id": "c1"})


# --- LLM plan output happy path ---

def test_llm_plan_output_happy(valid_llm_output_dict: dict) -> None:
    out = LLMPlanOutput.model_validate(valid_llm_output_dict)
    assert len(out.sources) == 2
    assert isinstance(out.sources[0], ProductHuntSource)
    assert isinstance(out.sources[1], YCNewsSource)
    assert out.outreach_context is not None
    assert out.outreach_context.sequence_length == 3


def test_llm_plan_output_empty_sources_is_valid() -> None:
    """If the ICP doesn't justify any source, an empty plan is allowed."""
    out = LLMPlanOutput.model_validate({})
    assert out.sources == []
    assert out.global_filters is None
    assert out.outreach_context is None


# --- Closed schema ---

def test_llm_plan_output_extra_fields_rejected(valid_llm_output_dict: dict) -> None:
    bad = dict(valid_llm_output_dict)
    bad["unexpected"] = "oops"
    with pytest.raises(ValidationError):
        LLMPlanOutput.model_validate(bad)


def test_source_block_extra_filter_rejected() -> None:
    bad = {
        "sources": [
            {
                "source": "product_hunt",
                "enabled": True,
                "filters": {"topics": ["AI"], "not_a_real_filter": 1},
            }
        ]
    }
    with pytest.raises(ValidationError):
        LLMPlanOutput.model_validate(bad)


# --- Discriminated union routes filters to the right model ---

def test_unknown_source_rejected() -> None:
    bad = {"sources": [{"source": "made_up_source", "filters": {}}]}
    with pytest.raises(ValidationError):
        LLMPlanOutput.model_validate(bad)


def test_oc_status_must_be_one_of_three_values() -> None:
    bad = {"sources": [{"source": "open_corporates", "filters": {"status": "pending"}}]}
    with pytest.raises(ValidationError):
        LLMPlanOutput.model_validate(bad)


def test_oc_filters_route_to_open_corporates() -> None:
    plan = LLMPlanOutput.model_validate(
        {
            "sources": [
                {
                    "source": "open_corporates",
                    "filters": {
                        "jurisdiction_code": "us",
                        "status": "active",
                        "industry_keywords": ["software"],
                    },
                }
            ]
        }
    )
    src = plan.sources[0]
    assert src.source == "open_corporates"
    assert src.filters.jurisdiction_code == "us"


# --- Global filters ---

def test_employee_count_range_max_must_be_ge_min() -> None:
    with pytest.raises(ValidationError):
        EmployeeCountRange.model_validate({"min": 100, "max": 50})


def test_global_filters_optional() -> None:
    gf = GlobalFilters.model_validate({})
    assert gf.exclude_domains is None
    assert gf.employee_count_range is None


def test_global_filters_extra_rejected() -> None:
    with pytest.raises(ValidationError):
        GlobalFilters.model_validate({"exclude_domains": [], "fake_key": True})


# --- Outreach context ---

def test_outreach_context_sequence_length_must_be_positive() -> None:
    with pytest.raises(ValidationError):
        OutreachContext.model_validate({"sequence_length": 0})


# --- PlanRecord wraps LLMPlanOutput with metadata ---

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
    assert len(record.sources) == 2
