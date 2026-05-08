"""Jinja2-based email template engine with variable injection."""
from typing import Any


class TemplateEngine:
    """Render email templates with prospect and campaign data."""

    SUBJECT_TEMPLATE = "{{company_hook}} — {{value_prop}}"
    BODY_TEMPLATE = """Hi {{first_name}},

{{opening_line}}

{{body_paragraph}}

{{call_to_action}}

Best,
{{sender_name}}

---
{{unsubscribe_link}}"""

    def render_subject(self, variables: dict[str, Any]) -> str:
        result = self.SUBJECT_TEMPLATE
        for key, value in variables.items():
            result = result.replace("{{" + key + "}}", str(value))
        return result

    def render_body(self, variables: dict[str, Any]) -> str:
        result = self.BODY_TEMPLATE
        for key, value in variables.items():
            result = result.replace("{{" + key + "}}", str(value))
        return result

    def render(self, variables: dict[str, Any]) -> dict[str, str]:
        return {
            "subject": self.render_subject(variables),
            "body": self.render_body(variables),
        }

    @staticmethod
    def inject_unsubscribe(body: str, campaign_id: str, prospect_id: str) -> str:
        unsub_url = f"https://outreach.example.com/unsubscribe/{campaign_id}/{prospect_id}"
        unsub_link = f'<a href="{unsub_url}">Unsubscribe</a>'
        return body.replace("{{unsubscribe_link}}", unsub_link)
