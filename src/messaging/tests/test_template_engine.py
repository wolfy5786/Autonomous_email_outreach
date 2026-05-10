"""Unit tests for the email template engine."""
from src.messaging.messaging.template_engine import TemplateEngine


def test_render_subject():
    engine = TemplateEngine()
    result = engine.render_subject({
        "company_hook": "Loved your Series A news",
        "value_prop": "let's explore a partnership",
    })
    assert "Loved your Series A news" in result
    assert "partnership" in result


def test_render_body():
    engine = TemplateEngine()
    result = engine.render_body({
        "first_name": "Sarah",
        "opening_line": "Congrats on the recent launch!",
        "body_paragraph": "We help companies like yours scale outreach.",
        "call_to_action": "Would 15 min next week work?",
        "sender_name": "Krishna",
        "unsubscribe_link": "https://example.com/unsub",
    })
    assert "Sarah" in result
    assert "Krishna" in result
    assert "15 min" in result


def test_inject_unsubscribe():
    body = "Hello {{unsubscribe_link}}"
    result = TemplateEngine.inject_unsubscribe(body, "camp-1", "prospect-1")
    assert "unsubscribe/camp-1/prospect-1" in result
    assert "<a href=" in result
