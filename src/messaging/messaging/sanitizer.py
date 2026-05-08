"""Sanitize LLM-generated email content before sending."""
import re
from typing import Optional


class DraftSanitizer:
    """Clean and validate LLM output for email drafts."""

    # Patterns that indicate the LLM hallucinated or leaked prompt
    BLOCKED_PATTERNS = [
        r"as an ai",
        r"as a language model",
        r"i cannot",
        r"i'?m sorry",
        r"\[insert",
        r"\{insert",
        r"<placeholder>",
        r"dear \[",
    ]

    MAX_SUBJECT_LENGTH = 120
    MAX_BODY_LENGTH = 5000

    def sanitize_subject(self, subject: str) -> str:
        subject = subject.strip().strip('"').strip("'")
        subject = re.sub(r"\s+", " ", subject)
        if len(subject) > self.MAX_SUBJECT_LENGTH:
            subject = subject[: self.MAX_SUBJECT_LENGTH - 3] + "..."
        return subject

    def sanitize_body(self, body: str) -> str:
        # Remove any markdown code fences the LLM might have added
        body = re.sub(r"```[\s\S]*?```", "", body)
        body = body.strip()
        if len(body) > self.MAX_BODY_LENGTH:
            body = body[: self.MAX_BODY_LENGTH]
        return body

    def check_blocked(self, text: str) -> Optional[str]:
        lower = text.lower()
        for pattern in self.BLOCKED_PATTERNS:
            if re.search(pattern, lower):
                return f"Blocked pattern detected: {pattern}"
        return None

    def sanitize(self, subject: str, body: str) -> dict:
        blocked = self.check_blocked(subject) or self.check_blocked(body)
        if blocked:
            return {"ok": False, "error": blocked, "subject": subject, "body": body}

        return {
            "ok": True,
            "subject": self.sanitize_subject(subject),
            "body": self.sanitize_body(body),
        }
