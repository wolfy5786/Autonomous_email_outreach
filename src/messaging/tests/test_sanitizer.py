"""Unit tests for the draft sanitizer."""
from src.messaging.messaging.sanitizer import DraftSanitizer


def test_clean_draft_passes():
    s = DraftSanitizer()
    result = s.sanitize(
        subject="Partnership opportunity with Acme",
        body="Hi John, I noticed your company..."
    )
    assert result["ok"] is True


def test_blocked_ai_mention():
    s = DraftSanitizer()
    result = s.sanitize(
        subject="Hello",
        body="As an AI language model, I cannot actually send emails."
    )
    assert result["ok"] is False
    assert "Blocked pattern" in result["error"]


def test_subject_truncation():
    s = DraftSanitizer()
    long_subject = "A" * 200
    result = s.sanitize(subject=long_subject, body="Valid body")
    assert result["ok"] is True
    assert len(result["subject"]) <= 120


def test_blocked_placeholder():
    s = DraftSanitizer()
    result = s.sanitize(
        subject="Hello [Insert Name]",
        body="This is fine"
    )
    assert result["ok"] is False


def test_code_fence_removal():
    s = DraftSanitizer()
    body = "Hello\n```python\nprint('hi')\n```\nGoodbye"
    result = s.sanitize(subject="Test", body=body)
    assert result["ok"] is True
    assert "```" not in result["body"]
