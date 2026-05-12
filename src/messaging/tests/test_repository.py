from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from messaging.repository import MessagingRepository
from messaging.schemas import (
    DraftStatus,
    EmailProvider,
    LLMUsage,
)


# ── ping ────────────────────────────────────────────────────────

class TestPing:
    async def test_returns_true_when_db_is_reachable(self, repo: MessagingRepository):
        assert await repo.ping() is True


# ── get_campaign_email_account ──────────────────────────────────

class TestGetCampaignEmailAccount:
    async def test_reads_via_underscore_id(self, repo: MessagingRepository):
        await repo.db["campaigns"].insert_one(
            {
                "_id": "c1",
                "config": {"email_account": {"provider": "gmail", "credentials_ref": "alice"}},
            }
        )
        ea = await repo.get_campaign_email_account("c1")
        assert ea is not None
        assert ea.provider is EmailProvider.GMAIL
        assert ea.credentials_ref == "alice"

    async def test_falls_back_to_id_field(self, repo: MessagingRepository):
        await repo.db["campaigns"].insert_one(
            {
                "id": "c2",
                "config": {"email_account": {"provider": "gmail", "credentials_ref": "bob"}},
            }
        )
        ea = await repo.get_campaign_email_account("c2")
        assert ea is not None and ea.credentials_ref == "bob"

    async def test_missing_campaign_returns_none(self, repo: MessagingRepository):
        assert await repo.get_campaign_email_account("nope") is None

    async def test_campaign_without_email_account_returns_none(self, repo: MessagingRepository):
        await repo.db["campaigns"].insert_one({"_id": "c3", "config": {}})
        assert await repo.get_campaign_email_account("c3") is None

    async def test_campaign_without_config_returns_none(self, repo: MessagingRepository):
        await repo.db["campaigns"].insert_one({"_id": "c4"})
        assert await repo.get_campaign_email_account("c4") is None


# ── get_poc ─────────────────────────────────────────────────────

class TestGetPoc:
    async def test_reads_minimal_poc(self, repo: MessagingRepository):
        await repo.db["persons"].insert_one(
            {"_id": "p1", "company_id": "co1", "email": "sam@acme.com"}
        )
        poc = await repo.get_poc("p1")
        assert poc is not None
        assert poc.email == "sam@acme.com"
        assert poc.id == "p1"

    async def test_missing_returns_none(self, repo: MessagingRepository):
        assert await repo.get_poc("nope") is None

    async def test_invalid_poc_without_email_raises(self, repo: MessagingRepository):
        # Surfaces ValidationError loudly — handler treats this as fatal/DLQ.
        await repo.db["persons"].insert_one({"_id": "p2", "company_id": "co1"})
        with pytest.raises(ValidationError):
            await repo.get_poc("p2")


# ── get_company ─────────────────────────────────────────────────

class TestGetCompany:
    async def test_reads_company(self, repo: MessagingRepository):
        await repo.db["companies"].insert_one(
            {"_id": "co1", "name": "Acme", "domain": "acme.com", "industry": "saas"}
        )
        company = await repo.get_company("co1")
        assert company is not None
        assert company.name == "Acme"
        assert company.industry == "saas"

    async def test_missing_returns_none(self, repo: MessagingRepository):
        assert await repo.get_company("nope") is None


# ── get_plan_by_campaign ────────────────────────────────────────

class TestGetPlanByCampaign:
    async def test_finds_plan_for_campaign(self, repo: MessagingRepository):
        await repo.db["plans"].insert_one(
            {
                "_id": "pl1",
                "campaign_id": "c1",
                "email_tone": "warm",
                "email_angle": "save eng time",
                "personalization_hooks": ["recent_funding"],
            }
        )
        plan = await repo.get_plan_by_campaign("c1")
        assert plan is not None
        assert plan.email_tone == "warm"
        assert plan.personalization_hooks == ["recent_funding"]

    async def test_missing_returns_none(self, repo: MessagingRepository):
        assert await repo.get_plan_by_campaign("nope") is None


# ── top_hints ───────────────────────────────────────────────────

class TestTopHints:
    async def test_sorted_by_relevance_and_limited(self, repo: MessagingRepository):
        for category, score in [("funding", 0.4), ("hiring", 0.9), ("news", 0.6)]:
            await repo.db["hints"].insert_one(
                {
                    "company_id": "co1",
                    "campaign_id": "c1",
                    "category": category,
                    "summary": f"{category} happened",
                    "source_name": "serp",
                    "source_type": "serp",
                    "relevance_score": score,
                }
            )
        hints = await repo.top_hints("co1", "c1", limit=2)
        assert [h.category for h in hints] == ["hiring", "news"]

    async def test_empty_returns_empty_list(self, repo: MessagingRepository):
        hints = await repo.top_hints("co_x", "c_x")
        assert hints == []

    async def test_filters_by_company_and_campaign(self, repo: MessagingRepository):
        await repo.db["hints"].insert_one(
            {
                "company_id": "co1", "campaign_id": "c1", "category": "news",
                "summary": "x", "source_name": "s", "source_type": "serp",
                "relevance_score": 0.5,
            }
        )
        await repo.db["hints"].insert_one(
            {
                "company_id": "co_other", "campaign_id": "c1", "category": "news",
                "summary": "y", "source_name": "s", "source_type": "serp",
                "relevance_score": 0.99,
            }
        )
        hints = await repo.top_hints("co1", "c1")
        assert len(hints) == 1
        assert hints[0].summary == "x"


# ── find_existing_draft ─────────────────────────────────────────

class TestFindExistingDraft:
    async def test_returns_existing_draft(self, repo: MessagingRepository):
        await repo.db["email_drafts"].insert_one(
            {
                "_id": "d1", "id": "d1",
                "campaign_id": "c1", "company_id": "co1", "poc_id": "p1",
                "status": "draft_created",
                "email_draft_ref": "gmail-1",
                "email_provider": "gmail",
                "retry_count": 0,
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        draft = await repo.find_existing_draft("c1", "p1")
        assert draft is not None
        assert draft.status is DraftStatus.DRAFT_CREATED
        assert draft.email_draft_ref == "gmail-1"

    async def test_missing_returns_none(self, repo: MessagingRepository):
        assert await repo.find_existing_draft("c1", "nope") is None


# ── upsert_generating_draft ─────────────────────────────────────

class TestUpsertGeneratingDraft:
    async def test_inserts_new_row(self, repo: MessagingRepository):
        draft_id, retry = await repo.upsert_generating_draft(
            new_draft_id="d-new",
            campaign_id="c1", company_id="co1", poc_id="p1",
        )
        assert (draft_id, retry) == ("d-new", 0)
        doc = await repo.db["email_drafts"].find_one({"_id": "d-new"})
        assert doc is not None
        assert doc["status"] == "generating"
        assert doc["retry_count"] == 0

    async def test_resume_increments_retry_and_reuses_id(self, repo: MessagingRepository):
        # First attempt
        first_id, _ = await repo.upsert_generating_draft(
            new_draft_id="d-first",
            campaign_id="c1", company_id="co1", poc_id="p1",
        )
        await repo.mark_failed(first_id, error="boom")

        # Redelivery: caller supplies a new candidate id but repo reuses existing
        second_id, retry = await repo.upsert_generating_draft(
            new_draft_id="d-ignored",
            campaign_id="c1", company_id="co1", poc_id="p1",
        )
        assert second_id == "d-first"
        assert retry == 1

        doc = await repo.db["email_drafts"].find_one({"_id": "d-first"})
        assert doc["status"] == "generating"
        assert doc["retry_count"] == 1
        assert doc["error"] is None  # cleared on resume


# ── mark_failed / mark_draft_created ────────────────────────────

class TestMarkFailed:
    async def test_sets_status_and_error(self, repo: MessagingRepository):
        await repo.upsert_generating_draft(
            new_draft_id="d1", campaign_id="c1", company_id="co1", poc_id="p1",
        )
        await repo.mark_failed("d1", error="provider exploded")
        doc = await repo.db["email_drafts"].find_one({"_id": "d1"})
        assert doc["status"] == "failed"
        assert doc["error"] == "provider exploded"


class TestMarkDraftCreated:
    async def test_sets_all_fields_with_usage(self, repo: MessagingRepository):
        await repo.upsert_generating_draft(
            new_draft_id="d1", campaign_id="c1", company_id="co1", poc_id="p1",
        )
        await repo.mark_draft_created(
            "d1",
            subject="Hi Sam",
            body="hello there. " * 5,
            hooks=["recent_funding"],
            provider=EmailProvider.GMAIL,
            email_draft_ref="gmail-xyz",
            llm_model="gemini/gemini-1.5-pro",
            llm_usage=LLMUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150),
        )
        doc = await repo.db["email_drafts"].find_one({"_id": "d1"})
        assert doc["status"] == "draft_created"
        assert doc["subject"] == "Hi Sam"
        assert doc["personalization_hooks"] == ["recent_funding"]
        assert doc["email_provider"] == "gmail"
        assert doc["email_draft_ref"] == "gmail-xyz"
        assert doc["llm_model"] == "gemini/gemini-1.5-pro"
        assert doc["llm_usage"] == {
            "prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150,
        }
        assert doc["error"] is None

    async def test_works_without_optional_usage(self, repo: MessagingRepository):
        await repo.upsert_generating_draft(
            new_draft_id="d2", campaign_id="c1", company_id="co1", poc_id="p2",
        )
        await repo.mark_draft_created(
            "d2",
            subject="hello",
            body="hello there. " * 5,
            hooks=["x"],
            provider=EmailProvider.STUB,
            email_draft_ref="stub-1",
        )
        doc = await repo.db["email_drafts"].find_one({"_id": "d2"})
        assert doc["status"] == "draft_created"
        assert doc.get("llm_model") is None
        assert doc.get("llm_usage") is None
