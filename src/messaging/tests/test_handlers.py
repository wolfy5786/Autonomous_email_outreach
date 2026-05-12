from unittest.mock import AsyncMock

import pytest

from local_infrastructure.factory.broker_interface import NonRetryableError
from messaging.config import Settings
from messaging.credentials import CredentialsResolver
from messaging.handlers import handle_messaging_requested
from messaging.providers import StubDraftProvider
from messaging.schemas import LLMDraftOutput, LLMUsage


# ── Fixtures ────────────────────────────────────────────────────

@pytest.fixture
def settings():
    return Settings(broker_type="rabbitmq", llm_model="test/model")


@pytest.fixture
def credentials():
    return CredentialsResolver(
        client_id="cid",
        client_secret="cs",
        env={"GMAIL_REFRESH_TOKEN_ALICE": "rt-1"},
    )


@pytest.fixture
def stub_provider():
    return StubDraftProvider()


@pytest.fixture
def llm_fn_ok():
    return AsyncMock(
        return_value=(
            LLMDraftOutput(
                subject="Quick question",
                body="Hi Sam — saw the Series B last month. " * 4,
                personalization_hooks=["funding"],
            ),
            LLMUsage(prompt_tokens=10, completion_tokens=20, total_tokens=30),
        )
    )


@pytest.fixture
def broker():
    """Records publishes for assertion."""
    return AsyncMock()


def _msg(campaign_id: str = "c1", poc_id: str = "p1", trace_id: str | None = None):
    m: dict = {"campaign_id": campaign_id, "poc_id": poc_id}
    if trace_id:
        m["trace_id"] = trace_id
    return m


async def _seed_full(repo):
    """Seed a complete campaign + plan + person + company.

    Matches the contract that the Step 11 mock seeder will materialize. When
    Prospecting lands its real model, the shape under `persons` is what it
    must produce.
    """
    await repo.db["campaigns"].insert_one(
        {
            "_id": "c1",
            "config": {"email_account": {"provider": "gmail", "credentials_ref": "alice"}},
        }
    )
    await repo.db["plans"].insert_one(
        {
            "_id": "pl1",
            "campaign_id": "c1",
            "email_tone": "warm",
            "email_angle": "save eng time",
            "personalization_hooks": [],
        }
    )
    await repo.db["companies"].insert_one(
        {"_id": "co1", "name": "Acme", "domain": "acme.com"}
    )
    await repo.db["persons"].insert_one(
        {
            "_id": "p1",
            "company_id": "co1",
            "first_name": "Sam",
            "email": "sam@acme.com",
            "email_verified": True,
        }
    )


async def _call(repo, llm_fn, provider, credentials, broker, settings, message=None):
    return await handle_messaging_requested(
        message or _msg(),
        repo=repo,
        llm_fn=llm_fn,
        provider=provider,
        credentials=credentials,
        broker=broker,
        settings=settings,
    )


# ── Happy path ──────────────────────────────────────────────────

class TestHappyPath:
    async def test_creates_draft_and_publishes_written(
        self, repo, llm_fn_ok, stub_provider, credentials, broker, settings
    ):
        await _seed_full(repo)
        await _call(repo, llm_fn_ok, stub_provider, credentials, broker, settings)

        # LLM called once with typed inputs
        kw = llm_fn_ok.await_args.kwargs
        assert kw["company"].name == "Acme"
        assert kw["poc"].email == "sam@acme.com"
        assert kw["plan"].email_tone == "warm"

        # Draft persisted
        doc = await repo.db["email_drafts"].find_one({"campaign_id": "c1", "poc_id": "p1"})
        assert doc["status"] == "draft_created"
        assert doc["subject"] == "Quick question"
        assert doc["personalization_hooks"] == ["funding"]
        assert doc["email_provider"] == "stub"
        assert doc["email_draft_ref"].startswith("stub-")
        assert doc["llm_model"] == "test/model"
        assert doc["llm_usage"]["total_tokens"] == 30

        # draft.written published
        broker.publish.assert_called_once()
        topic, payload = broker.publish.call_args.args
        assert topic == settings.draft_written_queue
        assert payload["campaign_id"] == "c1"
        assert payload["poc_id"] == "p1"
        assert payload["draft_id"] == doc["id"]
        assert payload["email_draft_ref"].startswith("stub-")


# ── Idempotent re-delivery ──────────────────────────────────────

class TestIdempotency:
    async def test_existing_draft_created_republishes_without_llm_call(
        self, repo, llm_fn_ok, stub_provider, credentials, broker, settings
    ):
        await _seed_full(repo)
        await repo.db["email_drafts"].insert_one(
            {
                "_id": "d-existing", "id": "d-existing",
                "campaign_id": "c1", "company_id": "co1", "poc_id": "p1",
                "status": "draft_created", "email_draft_ref": "gmail-prev",
                "email_provider": "gmail", "retry_count": 0,
                "subject": "x", "body": "y", "personalization_hooks": [],
                "generated_at": "2026-01-01T00:00:00",
            }
        )
        await _call(repo, llm_fn_ok, stub_provider, credentials, broker, settings)

        llm_fn_ok.assert_not_called()
        broker.publish.assert_called_once()
        _, payload = broker.publish.call_args.args
        assert payload["draft_id"] == "d-existing"
        assert payload["email_draft_ref"] == "gmail-prev"


# ── Missing-data unhappy paths ──────────────────────────────────

class TestMissingData:
    async def test_missing_campaign_raises_non_retryable(
        self, repo, llm_fn_ok, stub_provider, credentials, broker, settings
    ):
        # No seed — empty db.
        with pytest.raises(NonRetryableError, match="campaign"):
            await _call(repo, llm_fn_ok, stub_provider, credentials, broker, settings)
        llm_fn_ok.assert_not_called()
        broker.publish.assert_not_called()

    async def test_missing_plan_raises_non_retryable(
        self, repo, llm_fn_ok, stub_provider, credentials, broker, settings
    ):
        await repo.db["campaigns"].insert_one(
            {
                "_id": "c1",
                "config": {"email_account": {"provider": "gmail", "credentials_ref": "alice"}},
            }
        )
        with pytest.raises(NonRetryableError, match="plan"):
            await _call(repo, llm_fn_ok, stub_provider, credentials, broker, settings)
        llm_fn_ok.assert_not_called()
        broker.publish.assert_not_called()

    async def test_missing_poc_raises_non_retryable(
        self, repo, llm_fn_ok, stub_provider, credentials, broker, settings
    ):
        await repo.db["campaigns"].insert_one(
            {
                "_id": "c1",
                "config": {"email_account": {"provider": "gmail", "credentials_ref": "alice"}},
            }
        )
        await repo.db["plans"].insert_one(
            {"_id": "pl1", "campaign_id": "c1", "email_tone": "warm", "email_angle": "x"}
        )
        with pytest.raises(NonRetryableError, match="poc"):
            await _call(repo, llm_fn_ok, stub_provider, credentials, broker, settings)
        llm_fn_ok.assert_not_called()

    async def test_missing_company_raises_non_retryable(
        self, repo, llm_fn_ok, stub_provider, credentials, broker, settings
    ):
        await repo.db["campaigns"].insert_one(
            {
                "_id": "c1",
                "config": {"email_account": {"provider": "gmail", "credentials_ref": "alice"}},
            }
        )
        await repo.db["plans"].insert_one(
            {"_id": "pl1", "campaign_id": "c1", "email_tone": "warm", "email_angle": "x"}
        )
        await repo.db["persons"].insert_one(
            {"_id": "p1", "company_id": "co_missing", "email": "sam@acme.com"}
        )
        with pytest.raises(NonRetryableError, match="company"):
            await _call(repo, llm_fn_ok, stub_provider, credentials, broker, settings)
        llm_fn_ok.assert_not_called()


# ── Missing credentials ─────────────────────────────────────────

class TestMissingCredentials:
    async def test_unknown_credentials_ref_raises_non_retryable(
        self, repo, llm_fn_ok, stub_provider, broker, settings
    ):
        await _seed_full(repo)
        bad_creds = CredentialsResolver(
            client_id="cid", client_secret="cs", env={}  # ALICE not present
        )
        with pytest.raises(NonRetryableError, match="GMAIL_REFRESH_TOKEN_ALICE"):
            await _call(repo, llm_fn_ok, stub_provider, bad_creds, broker, settings)
        llm_fn_ok.assert_not_called()
        broker.publish.assert_not_called()


# ── Provider failure ────────────────────────────────────────────

class TestProviderFailure:
    async def test_provider_error_publishes_draft_failed_and_raises(
        self, repo, llm_fn_ok, credentials, broker, settings
    ):
        await _seed_full(repo)
        bad_provider = AsyncMock()
        bad_provider.create_draft = AsyncMock(side_effect=RuntimeError("provider boom"))

        with pytest.raises(RuntimeError, match="provider boom"):
            await _call(repo, llm_fn_ok, bad_provider, credentials, broker, settings)

        doc = await repo.db["email_drafts"].find_one({"campaign_id": "c1", "poc_id": "p1"})
        assert doc["status"] == "failed"
        assert "provider boom" in doc["error"]

        broker.publish.assert_called_once()
        topic, payload = broker.publish.call_args.args
        assert topic == settings.draft_failed_queue
        assert "provider boom" in payload["error"]
        assert payload["draft_id"] == doc["id"]


# ── LLM failure ─────────────────────────────────────────────────

class TestLLMFailure:
    async def test_llm_error_publishes_draft_failed_and_raises(
        self, repo, stub_provider, credentials, broker, settings
    ):
        await _seed_full(repo)
        bad_llm = AsyncMock(side_effect=RuntimeError("llm boom"))

        with pytest.raises(RuntimeError, match="llm boom"):
            await _call(repo, bad_llm, stub_provider, credentials, broker, settings)

        doc = await repo.db["email_drafts"].find_one({"campaign_id": "c1", "poc_id": "p1"})
        assert doc["status"] == "failed"
        # Provider was never called → no email_draft_ref persisted
        assert doc.get("email_draft_ref") is None

        broker.publish.assert_called_once()
        topic, payload = broker.publish.call_args.args
        assert topic == settings.draft_failed_queue
        assert "llm boom" in payload["error"]


# ── Retry attempt ───────────────────────────────────────────────

class TestRetryAttempt:
    async def test_resumes_with_incremented_retry_count(
        self, repo, llm_fn_ok, stub_provider, credentials, broker, settings
    ):
        await _seed_full(repo)
        # Simulate a prior failed attempt
        await repo.upsert_generating_draft(
            new_draft_id="d-orig", campaign_id="c1", company_id="co1", poc_id="p1",
        )
        await repo.mark_failed("d-orig", error="prior boom")

        await _call(repo, llm_fn_ok, stub_provider, credentials, broker, settings)

        doc = await repo.db["email_drafts"].find_one({"_id": "d-orig"})
        assert doc["status"] == "draft_created"
        assert doc["retry_count"] == 1
        assert doc["error"] is None

        # draft.written payload references the reused draft_id
        _, payload = broker.publish.call_args.args
        assert payload["draft_id"] == "d-orig"
