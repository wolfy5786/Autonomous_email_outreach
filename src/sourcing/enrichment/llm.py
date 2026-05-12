"""litellm wrappers for the enrichment operation LLM calls.

Mirrors the planning service's litellm usage (response_format=json_schema +
exponential retry) so the sourcing service can share provider configuration.
"""

from __future__ import annotations

import json
import logging

from pydantic import BaseModel, Field, ValidationError

from config import settings

log = logging.getLogger("sourcing.enrichment.llm")


def _retryable_litellm_exceptions() -> tuple[type[BaseException], ...]:
    """Lazy-import retryable litellm exception types (litellm is heavy)."""
    import litellm

    return (
        litellm.RateLimitError,
        litellm.APIConnectionError,
        litellm.Timeout,
        litellm.ServiceUnavailableError,
        litellm.InternalServerError,
    )


class LLMExtractionError(Exception):
    """Raised when the LLM cannot produce a usable structured response."""


class LinkedInPocExtraction(BaseModel):
    """Parsed output of the LinkedIn POC extractor (operation 1)."""

    poc_name: str | None = Field(
        default=None,
        description="Best point-of-contact name visible on the page.",
    )
    poc_title: str | None = Field(
        default=None,
        description="Role/title shown next to the POC.",
    )
    poc_profile_url: str | None = Field(
        default=None,
        description="Profile URL if mentioned on the page; else null.",
    )
    rationale: str | None = Field(
        default=None,
        description="Short reasoning for why this POC was chosen.",
    )


_LINKEDIN_POC_SYSTEM = (
    "You are an extractor. Given the rendered text of one LinkedIn company "
    "page, pick a single best point-of-contact for outbound sales or "
    "partnership outreach.\n"
    "Prefer founders, CEOs, heads of GTM/Sales/BD, or the most senior person "
    "visible. Use only information present in the provided text. If no person "
    "is visible, return nulls.\n"
    "Respond as JSON matching the requested schema."
)

_LINKEDIN_POC_USER_TEMPLATE = (
    "Company: {company_name}\n"
    "Source URL: {source_url}\n"
    "\n"
    "--- Page text (LinkedIn, single page, may be truncated) ---\n"
    "{page_markdown}\n"
    "--- end page text ---\n"
    "\n"
    "Return JSON with: poc_name, poc_title, poc_profile_url, rationale. "
    "Set fields to null when not present in the text."
)


def _truncate(text: str, limit: int) -> str:
    if limit <= 0 or len(text) <= limit:
        return text
    return text[:limit] + "\n…[truncated]"


async def extract_linkedin_poc(
    *,
    company_name: str,
    source_url: str,
    page_markdown: str,
) -> LinkedInPocExtraction:
    import litellm
    from tenacity import (
        AsyncRetrying,
        RetryError,
        retry_if_exception_type,
        stop_after_attempt,
        wait_exponential,
    )

    user_content = _LINKEDIN_POC_USER_TEMPLATE.format(
        company_name=company_name,
        source_url=source_url,
        page_markdown=_truncate(page_markdown, settings.enrichment_llm_max_chars),
    )
    messages = [
        {"role": "system", "content": _LINKEDIN_POC_SYSTEM},
        {"role": "user", "content": user_content},
    ]

    try:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(settings.enrichment_llm_max_retries),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            retry=retry_if_exception_type(_retryable_litellm_exceptions()),
            reraise=True,
        ):
            with attempt:
                resp = await litellm.acompletion(
                    model=settings.enrichment_llm_model,
                    messages=messages,
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": "linkedin_poc",
                            "schema": LinkedInPocExtraction.model_json_schema(),
                        },
                    },
                    temperature=settings.enrichment_llm_temperature,
                    max_tokens=settings.enrichment_llm_max_tokens,
                    timeout=settings.enrichment_llm_timeout_seconds,
                )
                content = resp.choices[0].message.content or ""
                return _parse_poc(content)
    except RetryError as e:  # pragma: no cover
        raise LLMExtractionError("LLM retries exhausted") from e

    raise LLMExtractionError("LLM retry loop exited without result")


def _parse_poc(content: str) -> LinkedInPocExtraction:
    """Parse the model's JSON response, tolerating a stray code-fence wrapper."""
    try:
        return LinkedInPocExtraction.model_validate_json(content)
    except ValidationError:
        pass
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        # strip an optional leading language tag
        if "\n" in cleaned:
            cleaned = cleaned.split("\n", 1)[1]
    try:
        return LinkedInPocExtraction.model_validate(json.loads(cleaned))
    except (ValidationError, json.JSONDecodeError) as e:
        raise LLMExtractionError(f"LLM output invalid: {e}") from e
