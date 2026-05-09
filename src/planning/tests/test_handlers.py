from typing import Any

import pytest

from local_infrastructure.factory.broker_interface import NonRetryableError
from planning.config import settings
from planning.handlers import handle_plan_requested
from planning.schemas import CampaignRecord, LLMPlanOutput, LLMUsage


def _make_llm_fn(output_dict: dict[str, Any]):
    async def _llm_fn(icp: dict, product: dict) -> tuple[LLMPlanOutput, LLMUsage]:
        return LLMPlanOutput.model_validate(output_dict), LLMUsage(
            prompt_tokens=100, completion_tokens=200, total_tokens=300
        )

    return _llm_fn


async def test_handler_happy_path(fake_repo, fake_broker, valid_llm_output_dict, sample_icp, sample_product) -> None:
    fake_repo.campaigns["c1"] = CampaignRecord(id="c1", icp=sample_icp, product_profile=sample_product)

    await handle_plan_requested(
        {"campaign_id": "c1"},
        repo=fake_repo,
        llm_fn=_make_llm_fn(valid_llm_output_dict),
        broker=fake_broker,
    )

    assert "c1" in fake_repo.plans_by_campaign
    plan_id = fake_repo.plans_by_campaign["c1"]["id"]
    assert fake_repo.attached == [("c1", plan_id)]
    assert len(fake_broker.published) == 1
    topic, body = fake_broker.published[0]
    assert topic == settings.plan_ready_queue
    assert body == {"campaign_id": "c1", "plan_id": plan_id}


async def test_handler_idempotency_skips_llm_when_plan_exists(
    fake_repo, fake_broker, valid_llm_output_dict, sample_icp, sample_product
) -> None:
    fake_repo.campaigns["c1"] = CampaignRecord(id="c1", icp=sample_icp, product_profile=sample_product)
    fake_repo.plans_by_campaign["c1"] = {"id": "11111111-1111-1111-1111-111111111111"}

    llm_calls: list[tuple[dict, dict]] = []

    async def counting_llm(icp: dict, product: dict) -> tuple[LLMPlanOutput, LLMUsage]:
        llm_calls.append((icp, product))
        return LLMPlanOutput.model_validate(valid_llm_output_dict), LLMUsage()

    await handle_plan_requested(
        {"campaign_id": "c1"}, repo=fake_repo, llm_fn=counting_llm, broker=fake_broker
    )

    assert llm_calls == []
    assert fake_broker.published == [
        (settings.plan_ready_queue, {"campaign_id": "c1", "plan_id": "11111111-1111-1111-1111-111111111111"})
    ]


async def test_handler_campaign_missing_raises_non_retryable(
    fake_repo, fake_broker, valid_llm_output_dict
) -> None:
    with pytest.raises(NonRetryableError):
        await handle_plan_requested(
            {"campaign_id": "nope"},
            repo=fake_repo,
            llm_fn=_make_llm_fn(valid_llm_output_dict),
            broker=fake_broker,
        )

    assert fake_broker.published == []


async def test_handler_duplicate_key_race_publishes_existing_id(
    fake_repo, fake_broker, valid_llm_output_dict, sample_icp, sample_product
) -> None:
    fake_repo.campaigns["c1"] = CampaignRecord(id="c1", icp=sample_icp, product_profile=sample_product)
    fake_repo.save_raises_duplicate_on_first_call = True

    await handle_plan_requested(
        {"campaign_id": "c1"},
        repo=fake_repo,
        llm_fn=_make_llm_fn(valid_llm_output_dict),
        broker=fake_broker,
    )

    # Whatever plan_id the fake repo synthesized during the race is what we publish.
    expected_id = fake_repo.plans_by_campaign["c1"]["id"]
    assert fake_broker.published == [
        (settings.plan_ready_queue, {"campaign_id": "c1", "plan_id": expected_id})
    ]
    assert fake_repo.attached == [("c1", expected_id)]


async def test_handler_invalid_event_raises(fake_repo, fake_broker, valid_llm_output_dict) -> None:
    # Missing required `campaign_id` — the Pydantic validation error bubbles up,
    # the RabbitMQ adapter maps it to a DLQ reject.
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        await handle_plan_requested(
            {},
            repo=fake_repo,
            llm_fn=_make_llm_fn(valid_llm_output_dict),
            broker=fake_broker,
        )
