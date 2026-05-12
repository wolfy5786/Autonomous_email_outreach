#!/usr/bin/env python3
"""Error handling and retry classification tests for prospecting."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Tuple

from pika.exceptions import AMQPError
from pymongo.errors import PyMongoError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.errors import PermanentProcessingError, RetryableProcessingError  # noqa: E402
from app.main import AppState  # noqa: E402
from app.worker import ProspectingWorker  # noqa: E402


def _ok(message: str) -> Tuple[bool, str]:
    return True, message


def _fail(message: str) -> Tuple[bool, str]:
    return False, message


class FakeMongo:
    def __init__(self, campaign=None, plan=None, processed=False):
        self._campaign = campaign
        self._plan = plan
        self._processed = processed

    def is_event_processed(self, event_id, campaign_id=None):
        return self._processed

    def get_campaign(self, campaign_id):
        return self._campaign

    def get_plan(self, campaign_id):
        return self._plan

    def mark_event_processed(self, *args, **kwargs):
        return None

    def update_company_score(self, *args, **kwargs):
        return None

    def update_person_score(self, *args, **kwargs):
        return None

    def update_person_email_verified(self, *args, **kwargs):
        return None

    def get_companies(self, company_ids):
        return []

    def get_persons_for_companies(self, company_ids):
        return []


class FakeBroker:
    def __init__(self, publish_error=None):
        self.publish_error = publish_error
        self.published = []

    def publish(self, routing_key, payload):
        if self.publish_error is not None:
            raise self.publish_error
        self.published.append((routing_key, payload))


class FakeWorker:
    def __init__(self, result=None, error=None):
        self.result = result or {"campaign_id": "campaign-1", "ranked_prospects": []}
        self.error = error

    def handle_prospecting_requested(self, msg):
        if self.error is not None:
            raise self.error
        return self.result


class FakeProps:
    def __init__(self, headers=None):
        self.headers = headers or {}


def _build_state(mongo, broker, worker) -> AppState:
    state = AppState.__new__(AppState)
    state.mongo = mongo
    state.broker = broker
    state.worker = worker
    state.settings = None
    state._consumer_thread = None
    return state


def test_missing_campaign_and_plan_classification() -> Tuple[bool, str]:
    try:
        missing_campaign_worker = ProspectingWorker(mongo=FakeMongo(campaign=None, plan=None), default_min_icp_score=0.0)
        try:
            missing_campaign_worker.handle_prospecting_requested({"campaign_id": "campaign-1", "plan_id": "plan-1", "entity_ids": []})
            return _fail("missing campaign was not rejected")
        except PermanentProcessingError:
            pass

        retryable_plan_worker = ProspectingWorker(
            mongo=FakeMongo(campaign={"id": "campaign-1", "status": "draft", "config": {}}, plan=None),
            default_min_icp_score=0.0,
        )
        try:
            retryable_plan_worker.handle_prospecting_requested({"campaign_id": "campaign-1", "plan_id": "plan-1", "entity_ids": []})
            return _fail("temporary missing plan was not retried")
        except RetryableProcessingError:
            pass

        permanent_plan_worker = ProspectingWorker(
            mongo=FakeMongo(campaign={"id": "campaign-1", "status": "active", "config": {}}, plan=None),
            default_min_icp_score=0.0,
        )
        try:
            permanent_plan_worker.handle_prospecting_requested({"campaign_id": "campaign-1", "plan_id": "plan-1", "entity_ids": []})
            return _fail("active campaign without plan was not rejected permanently")
        except PermanentProcessingError:
            pass

        return _ok("Missing campaign and plan states are classified correctly")
    except Exception as exc:
        return _fail(f"classification test failed: {exc}")


def test_retryable_mongo_and_publish_failures() -> Tuple[bool, str]:
    try:
        event = {"campaign_id": "campaign-1", "plan_id": "plan-1", "entity_ids": [], "event_id": "evt-1", "idempotency_key": "evt-1"}

        mongo_failure_state = _build_state(
            mongo=FakeMongo(campaign={"id": "campaign-1", "status": "active", "config": {}}, plan={"id": "plan-1", "campaign_id": "campaign-1", "company_signals": [], "poc_signals": [], "scoring_weights": {}}),
            broker=FakeBroker(),
            worker=FakeWorker(error=PyMongoError("db down")),
        )
        try:
            mongo_failure_state.handle_prospecting_requested_message(event, FakeProps())
            return _fail("mongo failure was not retried")
        except RetryableProcessingError:
            pass

        publish_failure_state = _build_state(
            mongo=FakeMongo(campaign={"id": "campaign-1", "status": "active", "config": {}}, plan={"id": "plan-1", "campaign_id": "campaign-1", "company_signals": [], "poc_signals": [], "scoring_weights": {}}),
            broker=FakeBroker(publish_error=AMQPError("publish down")),
            worker=FakeWorker(),
        )
        try:
            publish_failure_state.handle_prospecting_requested_message(event, FakeProps())
            return _fail("publish failure was not retried")
        except RetryableProcessingError:
            pass

        return _ok("Retryable failures are classified correctly for Mongo and publish errors")
    except Exception as exc:
        return _fail(f"retryable failure test failed: {exc}")


def test_duplicate_event_skip() -> Tuple[bool, str]:
    try:
        mongo = FakeMongo(campaign={"id": "campaign-1", "status": "active", "config": {}}, plan={"id": "plan-1", "campaign_id": "campaign-1", "company_signals": [], "poc_signals": [], "scoring_weights": {}})
        broker = FakeBroker()
        worker = FakeWorker()
        state = _build_state(mongo=mongo, broker=broker, worker=worker)
        state.handle_prospecting_requested_message({"campaign_id": "campaign-1", "plan_id": "plan-1", "entity_ids": [], "event_id": "evt-dup", "idempotency_key": "evt-dup"}, FakeProps())
        mongo._processed = True
        state.handle_prospecting_requested_message({"campaign_id": "campaign-1", "plan_id": "plan-1", "entity_ids": [], "event_id": "evt-dup", "idempotency_key": "evt-dup"}, FakeProps())
        if len(broker.published) != 1:
            return _fail("duplicate event was not skipped")
        return _ok("Duplicate events are skipped before publish")
    except Exception as exc:
        return _fail(f"duplicate skip test failed: {exc}")


def main() -> int:
    print("\n" + "=" * 50)
    print("ERROR HANDLING TESTS")
    print("=" * 50 + "\n")

    tests = [
        ("Missing Campaign / Plan Classification", test_missing_campaign_and_plan_classification),
        ("Retryable Mongo / Publish Failures", test_retryable_mongo_and_publish_failures),
        ("Duplicate Event Skip", test_duplicate_event_skip),
    ]

    all_passed = True
    for name, func in tests:
        passed, message = func()
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {name}")
        print(f"  {message}\n")
        if not passed:
            all_passed = False

    print("=" * 50)
    if all_passed:
        print("All error handling tests passed!")
        return 0

    print("Some error handling tests failed.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
