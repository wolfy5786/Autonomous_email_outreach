import pytest
from pydantic import ValidationError

from messaging.schemas import (
    CompanyContext,
    DraftFailedEvent,
    DraftWrittenEvent,
    EmailAccountConfig,
    EmailProvider,
    HintContext,
    LLMDraftOutput,
    MessagingRequestedEvent,
    PlanContext,
    PocRecord,
)


# ── MessagingRequestedEvent ─────────────────────────────────────

class TestMessagingRequestedEvent:
    def test_parses_minimal_payload(self):
        ev = MessagingRequestedEvent.model_validate({"campaign_id": "c1", "poc_id": "p1"})
        assert ev.campaign_id == "c1"
        assert ev.poc_id == "p1"
        assert ev.trace_id is None

    def test_accepts_optional_trace_id(self):
        ev = MessagingRequestedEvent.model_validate(
            {"campaign_id": "c1", "poc_id": "p1", "trace_id": "tr-1"}
        )
        assert ev.trace_id == "tr-1"

    def test_ignores_unknown_keys(self):
        # extra="ignore" — forward-compatible with future producer fields
        ev = MessagingRequestedEvent.model_validate(
            {"campaign_id": "c1", "poc_id": "p1", "future_field": 42}
        )
        assert ev.campaign_id == "c1"

    def test_rejects_missing_required(self):
        with pytest.raises(ValidationError):
            MessagingRequestedEvent.model_validate({"campaign_id": "c1"})


# ── DraftWrittenEvent / DraftFailedEvent ────────────────────────

class TestDraftEvents:
    def test_draft_written_happy(self):
        ev = DraftWrittenEvent(
            campaign_id="c1", draft_id="d1", poc_id="p1", email_draft_ref="gmail-abc"
        )
        assert ev.model_dump() == {
            "campaign_id": "c1",
            "draft_id": "d1",
            "poc_id": "p1",
            "email_draft_ref": "gmail-abc",
        }

    def test_draft_failed_defaults_retry_count(self):
        ev = DraftFailedEvent(campaign_id="c1", draft_id="d1", poc_id="p1", error="boom")
        assert ev.retry_count == 0

    def test_draft_written_requires_ref(self):
        with pytest.raises(ValidationError):
            DraftWrittenEvent(campaign_id="c1", draft_id="d1", poc_id="p1")


# ── LLMDraftOutput ──────────────────────────────────────────────

class TestLLMDraftOutput:
    def _valid(self, **overrides):
        base = {
            "subject": "Quick question about your platform team",
            "body": "Hi Sam — saw the Series B announcement. " * 4,
            "personalization_hooks": ["series_b_funding"],
        }
        base.update(overrides)
        return base

    def test_happy_path(self):
        out = LLMDraftOutput.model_validate(self._valid())
        assert out.subject.startswith("Quick")
        assert "Series B" in out.body

    def test_rejects_subject_too_short(self):
        with pytest.raises(ValidationError):
            LLMDraftOutput.model_validate(self._valid(subject="hi"))

    def test_rejects_body_too_short(self):
        with pytest.raises(ValidationError):
            LLMDraftOutput.model_validate(self._valid(body="hi"))

    def test_rejects_empty_hooks(self):
        with pytest.raises(ValidationError):
            LLMDraftOutput.model_validate(self._valid(personalization_hooks=[]))

    def test_rejects_extra_keys(self):
        # extra="forbid" — guards against the LLM smuggling in invented fields
        with pytest.raises(ValidationError):
            LLMDraftOutput.model_validate(self._valid(extra_field="nope"))


# ── PocRecord ───────────────────────────────────────────────────

class TestPocRecord:
    def test_parses_minimal(self):
        poc = PocRecord.model_validate(
            {"id": "p1", "company_id": "co1", "email": "sam@acme.com"}
        )
        assert poc.email == "sam@acme.com"
        assert poc.email_verified is False

    def test_ignores_extra_fields(self):
        # Forward-compat with future Prospecting Person model
        poc = PocRecord.model_validate(
            {"id": "p1", "company_id": "co1", "email": "x@y", "weird_extra": 1}
        )
        assert poc.id == "p1"

    def test_rejects_blank_id(self):
        with pytest.raises(ValidationError):
            PocRecord.model_validate({"id": "  ", "company_id": "co1", "email": "a@b"})

    def test_rejects_missing_email(self):
        # Without an email there's nothing to draft — fail loud.
        with pytest.raises(ValidationError):
            PocRecord.model_validate({"id": "p1", "company_id": "co1"})


# ── Lean context projections ────────────────────────────────────

class TestContextProjections:
    def test_company_context_min(self):
        c = CompanyContext.model_validate({"id": "co1", "name": "Acme", "domain": "acme.com"})
        assert c.industry is None

    def test_plan_context_defaults_hooks(self):
        p = PlanContext.model_validate(
            {"id": "pl1", "campaign_id": "c1", "email_tone": "warm", "email_angle": "save time"}
        )
        assert p.personalization_hooks == []

    def test_hint_context_optional_fields(self):
        h = HintContext.model_validate({"category": "funding", "summary": "Raised series B"})
        assert h.source_url is None
        assert h.relevance_score is None


# ── EmailAccountConfig ──────────────────────────────────────────

class TestEmailAccountConfig:
    def test_parses_gmail(self):
        cfg = EmailAccountConfig.model_validate(
            {"provider": "gmail", "credentials_ref": "alice"}
        )
        assert cfg.provider is EmailProvider.GMAIL

    def test_rejects_unknown_provider(self):
        with pytest.raises(ValidationError):
            EmailAccountConfig.model_validate(
                {"provider": "carrier_pigeon", "credentials_ref": "x"}
            )
