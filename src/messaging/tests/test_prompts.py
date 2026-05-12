import json

from messaging.prompts import (
    REPAIR_SYSTEM_SUFFIX,
    SYSTEM_PROMPT,
    USER_PROMPT_TEMPLATE,
    build_user_content,
)
from messaging.schemas import CompanyContext, HintContext, PlanContext, PocRecord


def _sample_inputs():
    plan = PlanContext(
        id="pl1", campaign_id="c1",
        email_tone="warm", email_angle="cut incident response time",
        personalization_hooks=["recent_funding"],
    )
    company = CompanyContext(
        id="co1", name="Acme", domain="acme.com", industry="devtools",
        description="Internal dev platform",
    )
    poc = PocRecord(
        id="p1", company_id="co1", first_name="Sam", last_name="Lee",
        title="VP Engineering", seniority="vp", department="engineering",
        email="sam@acme.com", email_verified=True,
    )
    hints = [
        HintContext(category="funding", summary="Raised $20M Series B in Mar 2026",
                    source_url="https://x.com/acme", relevance_score=0.9),
        HintContext(category="hiring", summary="Hiring 4 platform engineers",
                    source_url="https://acme.com/careers", relevance_score=0.7),
    ]
    return plan, company, poc, hints


class TestSystemPrompt:
    def test_states_grounding_constraint(self):
        assert "Use ONLY facts" in SYSTEM_PROMPT or "STAY GROUNDED" in SYSTEM_PROMPT

    def test_lists_valid_tones(self):
        for tone in ("consultative", "direct", "technical", "peer-to-peer", "warm", "executive-brief"):
            assert tone in SYSTEM_PROMPT

    def test_states_length_limits(self):
        assert "Subject" in SYSTEM_PROMPT and "80" in SYSTEM_PROMPT
        assert "140" in SYSTEM_PROMPT  # body word cap

    def test_demands_json_only_output(self):
        assert "JSON" in SYSTEM_PROMPT
        assert "personalization_hooks" in SYSTEM_PROMPT


class TestRepairSuffix:
    def test_template_includes_errors_placeholder(self):
        assert "{errors}" in REPAIR_SYSTEM_SUFFIX


class TestBuildUserContent:
    def test_renders_all_four_sections(self):
        plan, company, poc, hints = _sample_inputs()
        content = build_user_content(plan=plan, company=company, poc=poc, hints=hints)
        for label in ("POC ", "COMPANY:", "PLAN ", "HINTS"):
            assert label in content
        assert "sam@acme.com" in content
        assert "acme.com" in content
        assert "warm" in content
        assert "Series B" in content

    def test_hints_serialized_as_json_list(self):
        plan, company, poc, hints = _sample_inputs()
        content = build_user_content(plan=plan, company=company, poc=poc, hints=hints)
        # The hints section ends the template; isolate from the trailing instruction line.
        idx = content.index("HINTS")
        tail = content[idx:]
        json_start = tail.index("[")
        json_end = tail.rindex("]") + 1
        parsed = json.loads(tail[json_start:json_end])
        assert isinstance(parsed, list)
        assert any("Series B" in h["summary"] for h in parsed)

    def test_handles_empty_hints(self):
        plan, company, poc, _ = _sample_inputs()
        content = build_user_content(plan=plan, company=company, poc=poc, hints=[])
        assert "[]" in content


class TestUserPromptTemplate:
    def test_template_has_all_placeholders(self):
        for ph in ("{poc_json}", "{company_json}", "{plan_json}", "{hints_json}"):
            assert ph in USER_PROMPT_TEMPLATE
