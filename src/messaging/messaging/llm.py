import logging

import litellm
from pydantic import ValidationError
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .config import settings
from .prompts import REPAIR_SYSTEM_SUFFIX, SYSTEM_PROMPT, build_user_content
from .schemas import (
    CompanyContext,
    HintContext,
    LLMDraftOutput,
    LLMUsage,
    PlanContext,
    PocRecord,
)

log = logging.getLogger(__name__)

# Exceptions LiteLLM raises that are worth retrying.
_RETRYABLE_LITELLM = (
    litellm.RateLimitError,
    litellm.APIConnectionError,
    litellm.Timeout,
    litellm.ServiceUnavailableError,
    litellm.InternalServerError,
)


class LLMGenerationError(Exception):
    """Raised when the LLM cannot produce a valid draft after all retries."""


async def _single_call(messages: list[dict[str, str]]) -> tuple[str, LLMUsage]:
    resp = await litellm.acompletion(
        model=settings.llm_model,
        messages=messages,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "draft",
                "schema": LLMDraftOutput.model_json_schema(),
                "strict": True,
            },
        },
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        timeout=settings.llm_timeout_seconds,
    )
    content = resp.choices[0].message.content or ""
    usage_raw = getattr(resp, "usage", None)
    usage = LLMUsage.model_validate(usage_raw.model_dump() if usage_raw else {})
    return content, usage


async def generate_draft(
    *,
    plan: PlanContext,
    company: CompanyContext,
    poc: PocRecord,
    hints: list[HintContext],
) -> tuple[LLMDraftOutput, LLMUsage]:
    """Call the configured LLM and return a validated LLMDraftOutput.

    Retry strategy (mirrors planning):
      - Transient provider errors: exponential backoff, LLM_MAX_RETRIES attempts.
      - Schema validation failures: re-issue with a repair prompt containing the error,
        up to LLM_MAX_RETRIES attempts.
    """
    user_content = build_user_content(plan=plan, company=company, poc=poc, hints=hints)
    base_messages: list[dict[str, str]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]

    last_bad_output: str | None = None
    last_errors: str | None = None

    try:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(settings.llm_max_retries),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            retry=retry_if_exception_type(_RETRYABLE_LITELLM + (ValidationError,)),
            reraise=True,
        ):
            with attempt:
                messages = list(base_messages)
                if last_bad_output is not None and last_errors is not None:
                    messages[0] = {
                        "role": "system",
                        "content": SYSTEM_PROMPT + REPAIR_SYSTEM_SUFFIX.format(errors=last_errors),
                    }
                    messages.append({"role": "assistant", "content": last_bad_output})

                content, usage = await _single_call(messages)
                try:
                    parsed = LLMDraftOutput.model_validate_json(content)
                except ValidationError as e:
                    last_bad_output = content
                    last_errors = str(e)
                    log.warning("llm output failed validation, will retry with repair prompt")
                    raise
                return parsed, usage
    except RetryError as e:  # pragma: no cover — reraise=True makes this unlikely
        raise LLMGenerationError("LLM retries exhausted") from e
    except ValidationError as e:
        raise LLMGenerationError(f"LLM output invalid after retries: {e}") from e

    raise LLMGenerationError("LLM retry loop exited without result")
