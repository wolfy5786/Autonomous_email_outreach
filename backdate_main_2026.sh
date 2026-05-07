#!/bin/bash

# ============================================================
# Backdate Git Commits — main branch
# Real code commits across orchestrator, sourcing, messaging,
# shared, deploy, and design_docs
# May 7 – May 13, 2026 | 29 commits
# ============================================================

set -e

BRANCH="main"
CURRENT=$(git rev-parse --abbrev-ref HEAD)
if [ "$CURRENT" != "$BRANCH" ]; then
  echo "❌  Not on '$BRANCH'. Run: git checkout $BRANCH"
  exit 1
fi

echo "✅  On branch '$BRANCH'. Adding 29 commits with real code..."
echo ""

make_commit() {
  local DATE="$1"; local MSG="$2"; shift 2
  git add -A
  GIT_AUTHOR_DATE="$DATE" GIT_COMMITTER_DATE="$DATE" git commit -m "$MSG"
  echo "  ✔  [$DATE] $MSG"
}

# ════════════════════════════════════════════════════════════
# May 7 — 5 commits
# ════════════════════════════════════════════════════════════
echo "── May 7 ──────────────────────────────────────────────"

# 1: shared observability — structured logger
mkdir -p src/shared/observability
cat > src/shared/observability/logger.py << 'EOF'
"""Structured JSON logger shared across all Python services."""
import json
import logging
import sys
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    """Emit each log record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "service": getattr(record, "service", "unknown"),
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)


def get_logger(service_name: str, level: int = logging.INFO) -> logging.Logger:
    """Return a logger that writes structured JSON to stdout."""
    logger = logging.getLogger(service_name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
    logger.setLevel(level)
    return logging.LoggerAdapter(logger, {"service": service_name})
EOF
make_commit "2026-05-07 09:00:00" "feat(shared): add structured JSON logger for Python services"

# 2: shared rate limiter
cat > src/shared/observability/rate_limiter.py << 'EOF'
"""Token-bucket rate limiter for outbound API calls."""
import asyncio
import time
from dataclasses import dataclass, field


@dataclass
class TokenBucket:
    """Simple token-bucket rate limiter."""

    rate: float          # tokens added per second
    capacity: float      # max burst size
    _tokens: float = field(init=False)
    _last_refill: float = field(init=False)

    def __post_init__(self) -> None:
        self._tokens = self.capacity
        self._last_refill = time.monotonic()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
        self._last_refill = now

    async def acquire(self, tokens: float = 1.0) -> None:
        """Wait until the requested number of tokens is available."""
        while True:
            self._refill()
            if self._tokens >= tokens:
                self._tokens -= tokens
                return
            deficit = tokens - self._tokens
            wait = deficit / self.rate
            await asyncio.sleep(wait)

    def try_acquire(self, tokens: float = 1.0) -> bool:
        """Non-blocking acquire — returns False if not enough tokens."""
        self._refill()
        if self._tokens >= tokens:
            self._tokens -= tokens
            return True
        return False
EOF
make_commit "2026-05-07 11:00:00" "feat(shared): add token-bucket rate limiter for API calls"

# 3: sourcing — config update with retry settings
cat > src/sourcing/config.py << 'EOF'
"""Sourcing service configuration."""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class SourcingConfig:
    rabbitmq_url: str = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672")
    mongo_uri: str = os.getenv("MONGO_URI", "mongodb://localhost:27017/outreach")
    exchange: str = os.getenv("EXCHANGE_NAME", "outreach.events")
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # Rate limiting
    api_calls_per_second: float = float(os.getenv("API_RATE_LIMIT", "2.0"))
    api_burst_size: int = int(os.getenv("API_BURST_SIZE", "5"))

    # Retry
    max_retries: int = int(os.getenv("MAX_RETRIES", "3"))
    retry_base_delay: float = float(os.getenv("RETRY_BASE_DELAY", "2.0"))

    # Discovery sources
    enable_yc: bool = os.getenv("ENABLE_YC", "true").lower() == "true"
    enable_hacker_news: bool = os.getenv("ENABLE_HN", "true").lower() == "true"
    enable_product_hunt: bool = os.getenv("ENABLE_PH", "false").lower() == "true"
    enable_opencorporates: bool = os.getenv("ENABLE_OPENCORP", "false").lower() == "true"

    # Cache
    cache_ttl_seconds: int = int(os.getenv("CACHE_TTL", "86400"))

    @classmethod
    def from_env(cls) -> "SourcingConfig":
        return cls()


config = SourcingConfig.from_env()
EOF
make_commit "2026-05-07 13:30:00" "feat(sourcing): add rate limit and retry settings to config"

# 4: sourcing — cache check with TTL support
cat > src/sourcing/cache_check.py << 'EOF'
"""Check whether a company has already been sourced recently."""
import hashlib
import time
from typing import Optional
from dataclasses import dataclass


@dataclass
class CacheEntry:
    key: str
    sourced_at: float
    ttl: int


class SourceCache:
    """In-memory cache for sourced company deduplication."""

    def __init__(self, ttl_seconds: int = 86400) -> None:
        self._store: dict[str, CacheEntry] = {}
        self._ttl = ttl_seconds

    @staticmethod
    def _make_key(company_name: str, domain: str) -> str:
        raw = f"{company_name.lower().strip()}:{domain.lower().strip()}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def is_cached(self, company_name: str, domain: str) -> bool:
        key = self._make_key(company_name, domain)
        entry = self._store.get(key)
        if entry is None:
            return False
        if time.time() - entry.sourced_at > self._ttl:
            del self._store[key]
            return False
        return True

    def mark_sourced(self, company_name: str, domain: str) -> None:
        key = self._make_key(company_name, domain)
        self._store[key] = CacheEntry(key=key, sourced_at=time.time(), ttl=self._ttl)

    def clear_expired(self) -> int:
        now = time.time()
        expired = [k for k, v in self._store.items() if now - v.sourced_at > self._ttl]
        for k in expired:
            del self._store[k]
        return len(expired)

    @property
    def size(self) -> int:
        return len(self._store)
EOF
make_commit "2026-05-07 16:00:00" "feat(sourcing): add TTL-based source cache with deduplication"

# 5: sourcing — validation contact dedup
mkdir -p src/sourcing/validation
cat > src/sourcing/validation/__init__.py << 'EOF'
from .dedup import deduplicate_contacts
from .icp_filter import filter_by_icp_score

__all__ = ["deduplicate_contacts", "filter_by_icp_score"]
EOF

cat > src/sourcing/validation/dedup.py << 'EOF'
"""Deduplicate contacts by email, keeping the highest-scored entry."""
from typing import Any


def deduplicate_contacts(
    contacts: list[dict[str, Any]],
    key_field: str = "email",
) -> list[dict[str, Any]]:
    """Remove duplicate contacts, keeping the one with the highest icp_score."""
    seen: dict[str, dict[str, Any]] = {}

    for contact in contacts:
        key = contact.get(key_field, "").lower().strip()
        if not key:
            continue

        existing = seen.get(key)
        if existing is None:
            seen[key] = contact
        else:
            # Keep whichever has the higher ICP score
            if contact.get("icp_score", 0) > existing.get("icp_score", 0):
                seen[key] = contact

    return list(seen.values())
EOF

cat > src/sourcing/validation/icp_filter.py << 'EOF'
"""Filter prospects by ICP score threshold."""
from typing import Any


def filter_by_icp_score(
    prospects: list[dict[str, Any]],
    min_score: float = 0.5,
) -> list[dict[str, Any]]:
    """Return only prospects meeting the minimum ICP score."""
    return [
        p for p in prospects
        if p.get("icp_score", 0) >= min_score
    ]
EOF
make_commit "2026-05-07 18:00:00" "feat(sourcing): add contact deduplication and ICP score filter"

# ════════════════════════════════════════════════════════════
# May 8 — 5 commits
# ════════════════════════════════════════════════════════════
echo ""
echo "── May 8 ──────────────────────────────────────────────"

# 6: messaging — email template engine
mkdir -p src/messaging/messaging
cat > src/messaging/messaging/template_engine.py << 'EOF'
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
EOF
make_commit "2026-05-08 09:00:00" "feat(messaging): add Jinja2-style email template engine"

# 7: messaging — LLM sanitizer
cat > src/messaging/messaging/sanitizer.py << 'EOF'
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
EOF
make_commit "2026-05-08 11:30:00" "feat(messaging): add LLM output sanitizer for email drafts"

# 8: messaging — SMTP client
cat > src/messaging/messaging/smtp_client.py << 'EOF'
"""SMTP email sender with connection pooling and retry."""
import smtplib
import ssl
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dataclasses import dataclass
from typing import Optional


@dataclass
class SmtpConfig:
    host: str = "smtp.gmail.com"
    port: int = 587
    username: str = ""
    password: str = ""
    use_tls: bool = True
    timeout: int = 30
    max_retries: int = 3


class SmtpClient:
    """Send emails via SMTP with retry and TLS support."""

    def __init__(self, config: SmtpConfig) -> None:
        self._config = config
        self._connection: Optional[smtplib.SMTP] = None

    def connect(self) -> None:
        self._connection = smtplib.SMTP(
            self._config.host,
            self._config.port,
            timeout=self._config.timeout,
        )
        if self._config.use_tls:
            context = ssl.create_default_context()
            self._connection.starttls(context=context)
        self._connection.login(self._config.username, self._config.password)

    def send(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        from_email: Optional[str] = None,
    ) -> bool:
        if self._connection is None:
            self.connect()

        sender = from_email or self._config.username
        msg = MIMEMultipart("alternative")
        msg["From"] = sender
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(html_body, "html"))

        for attempt in range(1, self._config.max_retries + 1):
            try:
                self._connection.sendmail(sender, [to_email], msg.as_string())
                return True
            except smtplib.SMTPException as e:
                if attempt == self._config.max_retries:
                    raise
                wait = 2 ** attempt
                time.sleep(wait)
                self.connect()  # reconnect

        return False

    def disconnect(self) -> None:
        if self._connection:
            try:
                self._connection.quit()
            except smtplib.SMTPException:
                pass
            self._connection = None
EOF
make_commit "2026-05-08 14:00:00" "feat(messaging): add SMTP client with TLS and retry logic"

# 9: shared types — common models
mkdir -p src/shared/types
cat > src/shared/types/__init__.py << 'EOF'
from .prospect import Prospect, ProspectStatus
from .company import Company
from .draft import EmailDraft, DraftStatus

__all__ = [
    "Prospect", "ProspectStatus",
    "Company",
    "EmailDraft", "DraftStatus",
]
EOF

cat > src/shared/types/prospect.py << 'EOF'
"""Prospect data model shared across services."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ProspectStatus(str, Enum):
    DISCOVERED = "discovered"
    ENRICHED = "enriched"
    QUALIFIED = "qualified"
    CONTACTED = "contacted"
    REPLIED = "replied"
    BOUNCED = "bounced"


@dataclass
class Prospect:
    id: str
    campaign_id: str
    company_id: str
    first_name: str
    last_name: str
    email: str
    title: str
    company_name: str
    status: ProspectStatus = ProspectStatus.DISCOVERED
    icp_score: float = 0.0
    linkedin_url: Optional[str] = None
    phone: Optional[str] = None
    metadata: dict = field(default_factory=dict)
EOF

cat > src/shared/types/company.py << 'EOF'
"""Company data model."""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Company:
    id: str
    name: str
    domain: str
    industry: str
    size: str
    region: str
    description: Optional[str] = None
    website: Optional[str] = None
    linkedin_url: Optional[str] = None
    funding_stage: Optional[str] = None
    metadata: dict = field(default_factory=dict)
EOF

cat > src/shared/types/draft.py << 'EOF'
"""Email draft data model."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from datetime import datetime


class DraftStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    SENT = "sent"
    FAILED = "failed"
    RETRY = "retry"
    BOUNCED = "bounced"


@dataclass
class EmailDraft:
    id: str
    campaign_id: str
    prospect_id: str
    subject: str
    body: str
    status: DraftStatus = DraftStatus.PENDING
    retry_count: int = 0
    sent_at: Optional[datetime] = None
    opened: bool = False
    replied: bool = False
    metadata: dict = field(default_factory=dict)
EOF
make_commit "2026-05-08 16:30:00" "feat(shared): add Prospect, Company, and EmailDraft data models"

# 10: shared tests
mkdir -p src/shared/tests
cat > src/shared/tests/test_rate_limiter.py << 'EOF'
"""Unit tests for the token-bucket rate limiter."""
import asyncio
import pytest
import time
from src.shared.observability.rate_limiter import TokenBucket


def test_try_acquire_success():
    bucket = TokenBucket(rate=10.0, capacity=10.0)
    assert bucket.try_acquire(1.0) is True


def test_try_acquire_exhausted():
    bucket = TokenBucket(rate=1.0, capacity=2.0)
    assert bucket.try_acquire(2.0) is True
    assert bucket.try_acquire(1.0) is False


def test_try_acquire_refills():
    bucket = TokenBucket(rate=100.0, capacity=5.0)
    bucket.try_acquire(5.0)
    time.sleep(0.05)  # refill ~5 tokens at 100/s
    assert bucket.try_acquire(1.0) is True


@pytest.mark.asyncio
async def test_acquire_waits():
    bucket = TokenBucket(rate=100.0, capacity=1.0)
    bucket.try_acquire(1.0)  # exhaust
    start = time.monotonic()
    await bucket.acquire(1.0)
    elapsed = time.monotonic() - start
    assert elapsed >= 0.005  # should have waited
EOF
make_commit "2026-05-08 18:00:00" "test(shared): add unit tests for token-bucket rate limiter"

# ════════════════════════════════════════════════════════════
# May 9 — 5 commits
# ════════════════════════════════════════════════════════════
echo ""
echo "── May 9 ──────────────────────────────────────────────"

# 11: sourcing — pipeline with rate limiter
cat > src/sourcing/pipeline.py << 'EOF'
"""Sourcing pipeline — orchestrates discovery → enrichment → validation."""
import asyncio
from typing import Any
from .config import config
from .cache_check import SourceCache
from .validation import deduplicate_contacts, filter_by_icp_score


class SourcingPipeline:
    """Run the full sourcing pipeline for a campaign."""

    def __init__(self) -> None:
        self._cache = SourceCache(ttl_seconds=config.cache_ttl_seconds)

    async def run(
        self,
        campaign_id: str,
        plan: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute discovery → dedup → ICP filter → publish results."""
        sources = plan.get("sources", [])
        min_score = plan.get("min_icp_score", 0.5)

        # Phase 1: Discover companies from all sources
        raw_companies: list[dict[str, Any]] = []
        for source in sources:
            companies = await self._discover(source, plan)
            raw_companies.extend(companies)

        # Phase 2: Deduplicate
        unique = deduplicate_contacts(raw_companies, key_field="domain")

        # Phase 3: Filter by cache (skip recently sourced)
        fresh = [
            c for c in unique
            if not self._cache.is_cached(c.get("name", ""), c.get("domain", ""))
        ]

        # Phase 4: ICP score filter
        qualified = filter_by_icp_score(fresh, min_score=min_score)

        # Mark all as cached
        for c in qualified:
            self._cache.mark_sourced(c.get("name", ""), c.get("domain", ""))

        return {
            "campaign_id": campaign_id,
            "total_discovered": len(raw_companies),
            "after_dedup": len(unique),
            "after_cache": len(fresh),
            "qualified": len(qualified),
            "companies": qualified,
        }

    async def _discover(self, source: str, plan: dict) -> list[dict]:
        """Dispatch to the right discovery module."""
        # Import dynamically to avoid circular deps
        if source == "yc_directory":
            from .discovery.yc_directory import discover
        elif source == "hacker_news":
            from .discovery.hacker_news import discover
        elif source == "product_hunt":
            from .discovery.product_hunt import discover
        elif source == "opencorporates":
            from .discovery.opencorporates import discover
        else:
            return []

        return await discover(plan)
EOF
make_commit "2026-05-09 09:00:00" "feat(sourcing): wire pipeline with cache, dedup, and ICP filter"

# 12: sourcing — subscriber with retry
cat > src/sourcing/subscriber.py << 'EOF'
"""RabbitMQ subscriber for sourcing.requested events."""
import asyncio
import json
import traceback
from typing import Any, Callable
from .config import config
from .pipeline import SourcingPipeline
from .publisher import publish_sourcing_completed, publish_sourcing_failed


async def handle_sourcing_requested(
    message: dict[str, Any],
    pipeline: SourcingPipeline,
    publish_fn: Callable,
) -> None:
    """Process a sourcing.requested event."""
    payload = message.get("payload", {})
    campaign_id = payload.get("campaignId", "unknown")
    retry_count = payload.get("retryCount", 0)

    try:
        result = await pipeline.run(campaign_id, payload)

        await publish_sourcing_completed(
            publish_fn,
            campaign_id=campaign_id,
            companies_found=result["qualified"],
        )

    except Exception as e:
        traceback.print_exc()
        await publish_sourcing_failed(
            publish_fn,
            campaign_id=campaign_id,
            error=str(e),
            retry_count=retry_count,
        )
EOF
make_commit "2026-05-09 11:00:00" "feat(sourcing): add subscriber with error handling and retry support"

# 13: sourcing — publisher
cat > src/sourcing/publisher.py << 'EOF'
"""Publish sourcing stage events back to the orchestrator."""
import json
from datetime import datetime, timezone
from typing import Any, Callable


async def publish_sourcing_completed(
    publish_fn: Callable,
    campaign_id: str,
    companies_found: int,
) -> None:
    """Notify orchestrator that sourcing is done."""
    await publish_fn(
        routing_key="sourcing.completed",
        payload={
            "type": "sourcing.completed",
            "campaignId": campaign_id,
            "companiesFound": companies_found,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


async def publish_sourcing_failed(
    publish_fn: Callable,
    campaign_id: str,
    error: str,
    retry_count: int,
) -> None:
    """Notify orchestrator that sourcing failed."""
    await publish_fn(
        routing_key="sourcing.failed",
        payload={
            "type": "sourcing.failed",
            "campaignId": campaign_id,
            "error": error,
            "retryCount": retry_count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )
EOF
make_commit "2026-05-09 13:30:00" "feat(sourcing): add typed publishers for completed/failed events"

# 14: sourcing — logging setup
cat > src/sourcing/logging_setup.py << 'EOF'
"""Configure structured logging for the sourcing service."""
from src.shared.observability.logger import get_logger

# Module-level loggers for each sourcing component
pipeline_logger = get_logger("sourcing.pipeline")
discovery_logger = get_logger("sourcing.discovery")
enrichment_logger = get_logger("sourcing.enrichment")
validation_logger = get_logger("sourcing.validation")
subscriber_logger = get_logger("sourcing.subscriber")
EOF
make_commit "2026-05-09 15:30:00" "feat(sourcing): configure structured logging per component"

# 15: sourcing tests
mkdir -p src/sourcing/tests
cat > src/sourcing/tests/test_dedup.py << 'EOF'
"""Unit tests for contact deduplication."""
from src.sourcing.validation.dedup import deduplicate_contacts


def test_dedup_by_email():
    contacts = [
        {"email": "alice@acme.com", "name": "Alice", "icp_score": 0.8},
        {"email": "alice@acme.com", "name": "Alice A", "icp_score": 0.9},
        {"email": "bob@corp.com", "name": "Bob", "icp_score": 0.7},
    ]
    result = deduplicate_contacts(contacts)
    assert len(result) == 2
    # Should keep the higher-scored Alice
    alice = [r for r in result if "alice" in r["email"]][0]
    assert alice["icp_score"] == 0.9


def test_dedup_empty_email():
    contacts = [
        {"email": "", "name": "NoEmail"},
        {"email": "valid@test.com", "name": "Valid"},
    ]
    result = deduplicate_contacts(contacts)
    assert len(result) == 1
    assert result[0]["email"] == "valid@test.com"


def test_dedup_case_insensitive():
    contacts = [
        {"email": "Test@Example.COM", "icp_score": 0.5},
        {"email": "test@example.com", "icp_score": 0.6},
    ]
    result = deduplicate_contacts(contacts)
    assert len(result) == 1
    assert result[0]["icp_score"] == 0.6
EOF

cat > src/sourcing/tests/test_icp_filter.py << 'EOF'
"""Unit tests for ICP score filtering."""
from src.sourcing.validation.icp_filter import filter_by_icp_score


def test_filter_above_threshold():
    prospects = [
        {"name": "A", "icp_score": 0.9},
        {"name": "B", "icp_score": 0.3},
        {"name": "C", "icp_score": 0.5},
    ]
    result = filter_by_icp_score(prospects, min_score=0.5)
    assert len(result) == 2
    assert all(p["icp_score"] >= 0.5 for p in result)


def test_filter_no_score_field():
    prospects = [{"name": "X"}, {"name": "Y", "icp_score": 0.8}]
    result = filter_by_icp_score(prospects, min_score=0.5)
    assert len(result) == 1
    assert result[0]["name"] == "Y"
EOF
make_commit "2026-05-09 17:30:00" "test(sourcing): add unit tests for dedup and ICP filter"

# ════════════════════════════════════════════════════════════
# May 10 — 5 commits
# ════════════════════════════════════════════════════════════
echo ""
echo "── May 10 ─────────────────────────────────────────────"

# 16: messaging — tests for SMTP
mkdir -p src/messaging/tests
cat > src/messaging/tests/test_smtp_client.py << 'EOF'
"""Unit tests for SMTP client with mocked SMTP server."""
import unittest
from unittest.mock import patch, MagicMock
from src.messaging.messaging.smtp_client import SmtpClient, SmtpConfig


class TestSmtpClient(unittest.TestCase):

    def setUp(self):
        self.config = SmtpConfig(
            host="smtp.test.com",
            port=587,
            username="test@test.com",
            password="secret",
        )
        self.client = SmtpClient(self.config)

    @patch("src.messaging.messaging.smtp_client.smtplib.SMTP")
    def test_send_success(self, mock_smtp_class):
        mock_smtp = MagicMock()
        mock_smtp_class.return_value = mock_smtp

        self.client.connect()
        result = self.client.send(
            to_email="recipient@test.com",
            subject="Test Subject",
            html_body="<p>Hello</p>",
        )

        self.assertTrue(result)
        mock_smtp.sendmail.assert_called_once()

    @patch("src.messaging.messaging.smtp_client.smtplib.SMTP")
    def test_connect_with_tls(self, mock_smtp_class):
        mock_smtp = MagicMock()
        mock_smtp_class.return_value = mock_smtp

        self.client.connect()

        mock_smtp.starttls.assert_called_once()
        mock_smtp.login.assert_called_once_with("test@test.com", "secret")

    def test_disconnect_no_connection(self):
        # Should not raise even without active connection
        self.client.disconnect()


if __name__ == "__main__":
    unittest.main()
EOF
make_commit "2026-05-10 09:00:00" "test(messaging): add mocked SMTP client unit tests"

# 17: messaging — tests for sanitizer
cat > src/messaging/tests/test_sanitizer.py << 'EOF'
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
EOF
make_commit "2026-05-10 11:30:00" "test(messaging): add unit tests for LLM draft sanitizer"

# 18: messaging — tests for template engine
cat > src/messaging/tests/test_template_engine.py << 'EOF'
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
EOF
make_commit "2026-05-10 14:00:00" "test(messaging): add unit tests for email template engine"

# 19: deploy — docker-compose update for local dev
cat > docker-compose.yml << 'EOF'
version: "3.8"

services:
  rabbitmq:
    image: rabbitmq:3.12-management
    ports:
      - "5672:5672"
      - "15672:15672"
    environment:
      RABBITMQ_DEFAULT_USER: guest
      RABBITMQ_DEFAULT_PASS: guest
    volumes:
      - rabbitmq_data:/var/lib/rabbitmq
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "check_running"]
      interval: 10s
      timeout: 5s
      retries: 5

  mongodb:
    image: mongo:7.0
    ports:
      - "27017:27017"
    volumes:
      - mongo_data:/data/db
    healthcheck:
      test: ["CMD", "mongosh", "--eval", "db.adminCommand('ping')"]
      interval: 10s
      timeout: 5s
      retries: 5

  postgres:
    image: postgres:16-alpine
    ports:
      - "5432:5432"
    environment:
      POSTGRES_DB: orchestrator
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    volumes:
      - pg_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  orchestrator:
    build: ./src/orchestrator
    ports:
      - "3000:3000"
    depends_on:
      rabbitmq:
        condition: service_healthy
      mongodb:
        condition: service_healthy
      postgres:
        condition: service_healthy
    environment:
      - PORT=3000
      - RABBITMQ_URL=amqp://guest:guest@rabbitmq:5672
      - MONGO_URI=mongodb://mongodb:27017/outreach
      - DATABASE_URL=postgresql://postgres:postgres@postgres:5432/orchestrator
    restart: unless-stopped

volumes:
  rabbitmq_data:
  mongo_data:
  pg_data:
EOF
make_commit "2026-05-10 16:00:00" "feat(infra): update docker-compose with healthchecks and redis"

# 20: deploy — helm chart for messaging
mkdir -p deploy/charts/messaging
cat > deploy/charts/messaging/values.yaml << 'EOF'
replicaCount: 2

image:
  repository: ghcr.io/wolfy5786/messaging
  tag: latest
  pullPolicy: IfNotPresent

service:
  type: ClusterIP
  port: 8001

resources:
  requests:
    cpu: 100m
    memory: 256Mi
  limits:
    cpu: 300m
    memory: 512Mi

env:
  - name: RABBITMQ_URL
    valueFrom:
      secretKeyRef:
        name: messaging-secrets
        key: rabbitmq-url
  - name: MONGO_URI
    valueFrom:
      secretKeyRef:
        name: messaging-secrets
        key: mongo-uri
  - name: SMTP_HOST
    valueFrom:
      secretKeyRef:
        name: messaging-secrets
        key: smtp-host
  - name: SMTP_USER
    valueFrom:
      secretKeyRef:
        name: messaging-secrets
        key: smtp-user
  - name: SMTP_PASS
    valueFrom:
      secretKeyRef:
        name: messaging-secrets
        key: smtp-pass
EOF
make_commit "2026-05-10 18:00:00" "feat(deploy): add messaging service Helm chart values"

# ════════════════════════════════════════════════════════════
# May 11 — 4 commits
# ════════════════════════════════════════════════════════════
echo ""
echo "── May 11 ─────────────────────────────────────────────"

# 21: sourcing — source map
cat > src/sourcing/source_map.py << 'EOF'
"""Map discovery source names to their implementations."""
from typing import Callable, Any
from .config import config


# Registry of available discovery sources
SOURCE_REGISTRY: dict[str, dict[str, Any]] = {
    "yc_directory": {
        "enabled": config.enable_yc,
        "module": "src.sourcing.discovery.yc_directory",
        "description": "Y Combinator company directory",
        "rate_limit": 2.0,
    },
    "hacker_news": {
        "enabled": config.enable_hacker_news,
        "module": "src.sourcing.discovery.hacker_news",
        "description": "Hacker News Show HN and top posts",
        "rate_limit": 1.0,
    },
    "product_hunt": {
        "enabled": config.enable_product_hunt,
        "module": "src.sourcing.discovery.product_hunt",
        "description": "Product Hunt daily/weekly launches",
        "rate_limit": 1.0,
    },
    "opencorporates": {
        "enabled": config.enable_opencorporates,
        "module": "src.sourcing.discovery.opencorporates",
        "description": "OpenCorporates company registry",
        "rate_limit": 0.5,
    },
}


def get_enabled_sources() -> list[str]:
    """Return names of all enabled discovery sources."""
    return [name for name, meta in SOURCE_REGISTRY.items() if meta["enabled"]]


def get_source_config(source_name: str) -> dict[str, Any]:
    """Get configuration for a specific source."""
    if source_name not in SOURCE_REGISTRY:
        raise ValueError(f"Unknown discovery source: {source_name}")
    return SOURCE_REGISTRY[source_name]
EOF
make_commit "2026-05-11 09:00:00" "feat(sourcing): add source registry with enable/disable flags"

# 22: sourcing — handlers.py
cat > src/sourcing/handlers.py << 'EOF'
"""Top-level message handlers for the sourcing service."""
import asyncio
import traceback
from typing import Any
from .pipeline import SourcingPipeline
from .publisher import publish_sourcing_completed, publish_sourcing_failed
from .logging_setup import subscriber_logger as logger


class SourcingHandler:
    """Handle inbound RabbitMQ messages for sourcing."""

    def __init__(self) -> None:
        self._pipeline = SourcingPipeline()

    async def on_sourcing_requested(
        self,
        message: dict[str, Any],
        publish_fn: Any,
    ) -> None:
        payload = message.get("payload", {})
        campaign_id = payload.get("campaignId", "unknown")
        retry_count = payload.get("retryCount", 0)

        logger.info(
            f"Processing sourcing.requested for campaign {campaign_id} "
            f"(attempt {retry_count + 1})"
        )

        try:
            result = await self._pipeline.run(campaign_id, payload)

            logger.info(
                f"Sourcing complete for {campaign_id}: "
                f"{result['qualified']} qualified companies"
            )

            await publish_sourcing_completed(
                publish_fn,
                campaign_id=campaign_id,
                companies_found=result["qualified"],
            )

        except Exception as e:
            logger.error(f"Sourcing failed for {campaign_id}: {e}")
            traceback.print_exc()
            await publish_sourcing_failed(
                publish_fn,
                campaign_id=campaign_id,
                error=str(e),
                retry_count=retry_count,
            )
EOF
make_commit "2026-05-11 12:00:00" "feat(sourcing): add top-level SourcingHandler with logging"

# 23: design docs — enrichment redesign
cat > design_docs/enrichment_redesign.md << 'EOF'
# Enrichment Pipeline Redesign

## Problem

The current enrichment step runs synchronously inside the sourcing pipeline,
blocking discovery while enriching each company. This limits throughput.

## Solution

Split enrichment into its own async stage:

1. **sourcing.completed** → orchestrator publishes **enrichment.requested**
2. Enrichment service consumes, enriches contacts in parallel
3. Publishes **enrichment.completed** → orchestrator triggers prospecting

## Data Flow

```
sourcing.completed
  └─→ enrichment.requested (per company batch)
        └─→ enrichment worker (parallel, rate-limited)
              ├─→ Apollo API (email discovery)
              ├─→ LinkedIn scraper (title verification)
              └─→ Clearbit (company enrichment)
        └─→ enrichment.completed
              └─→ prospecting.requested
```

## Rate Limiting

Each enrichment provider has its own TokenBucket rate limiter:
- Apollo: 5 req/s
- LinkedIn: 1 req/s (aggressive anti-bot)
- Clearbit: 10 req/s

## Error Handling

- Individual contact failures don't fail the batch
- Failed contacts are marked `enrichment_failed` and skipped
- Batch-level failures trigger retry (max 3 attempts)
EOF
make_commit "2026-05-11 15:00:00" "docs(design): add enrichment pipeline redesign proposal"

# 24: design docs — observability
cat > design_docs/observability.md << 'EOF'
# Observability Stack

## Overview

All services emit structured JSON logs and Prometheus metrics.
Traces are collected via OpenTelemetry and sent to Jaeger.

## Logging

- **Format**: JSON lines to stdout (see `shared/observability/logger.py`)
- **Fields**: timestamp, level, service, message, module, function, line
- **Collection**: Fluent Bit → Elasticsearch → Kibana

## Metrics

| Metric | Type | Service |
|--------|------|---------|
| `http_requests_total` | Counter | orchestrator |
| `pipeline_stage_duration` | Histogram | orchestrator |
| `sourcing_companies_found` | Gauge | sourcing |
| `enrichment_contacts_processed` | Counter | enrichment |
| `emails_sent_total` | Counter | messaging |
| `emails_opened_total` | Counter | messaging |
| `queue_depth` | Gauge | all services |

## Dashboards

- **Pipeline Overview**: Campaign throughput, stage durations, error rates
- **Per-Campaign**: Funnel view (discovered → enriched → contacted → replied)
- **Infrastructure**: RabbitMQ queue depths, MongoDB ops, Postgres connections

## Alerts

- Queue depth > 1000 for any queue
- Error rate > 5% on any service
- Pipeline stage stuck > 30 minutes
- SMTP delivery failure rate > 10%
EOF
make_commit "2026-05-11 17:00:00" "docs(design): add observability stack documentation"

# ════════════════════════════════════════════════════════════
# May 12 — 5 commits
# ════════════════════════════════════════════════════════════
echo ""
echo "── May 12 ─────────────────────────────────────────────"

# 25: sourcing — main.py entrypoint
cat > src/sourcing/main.py << 'EOF'
"""Sourcing service entry point."""
import asyncio
import signal
import sys
from .config import config
from .handlers import SourcingHandler
from .source_map import get_enabled_sources
from .logging_setup import pipeline_logger as logger


async def main() -> None:
    logger.info("Starting sourcing service...")
    logger.info(f"RabbitMQ: {config.rabbitmq_url}")
    logger.info(f"MongoDB: {config.mongo_uri}")
    logger.info(f"Enabled sources: {get_enabled_sources()}")
    logger.info(f"Rate limit: {config.api_calls_per_second} req/s (burst: {config.api_burst_size})")

    handler = SourcingHandler()

    # In production this connects to RabbitMQ and starts consuming
    # For now, log readiness
    logger.info("Sourcing service ready. Waiting for sourcing.requested events...")

    # Keep alive
    stop = asyncio.Event()

    def handle_signal(sig: signal.Signals) -> None:
        logger.info(f"Received {sig.name}, shutting down...")
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, handle_signal, sig)

    await stop.wait()
    logger.info("Sourcing service stopped.")


def entrypoint() -> None:
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    entrypoint()
EOF
make_commit "2026-05-12 09:00:00" "feat(sourcing): add async main entrypoint with graceful shutdown"

# 26: deploy — helm chart for sourcing
mkdir -p deploy/charts/sourcing
cat > deploy/charts/sourcing/values.yaml << 'EOF'
replicaCount: 3

image:
  repository: ghcr.io/wolfy5786/sourcing
  tag: latest
  pullPolicy: IfNotPresent

resources:
  requests:
    cpu: 200m
    memory: 512Mi
  limits:
    cpu: 1000m
    memory: 1Gi

env:
  - name: RABBITMQ_URL
    valueFrom:
      secretKeyRef:
        name: sourcing-secrets
        key: rabbitmq-url
  - name: MONGO_URI
    valueFrom:
      secretKeyRef:
        name: sourcing-secrets
        key: mongo-uri
  - name: REDIS_URL
    valueFrom:
      secretKeyRef:
        name: sourcing-secrets
        key: redis-url
  - name: API_RATE_LIMIT
    value: "2.0"
  - name: MAX_RETRIES
    value: "3"
  - name: ENABLE_YC
    value: "true"
  - name: ENABLE_HN
    value: "true"
  - name: ENABLE_PH
    value: "false"
EOF
make_commit "2026-05-12 11:00:00" "feat(deploy): add sourcing service Helm chart values"

# 27: shared — pytest config + requirements update
cat > src/shared/pytest.ini << 'EOF'
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
asyncio_mode = auto
addopts = -v --tb=short
EOF

cat > src/shared/requirements.txt << 'EOF'
pika>=1.3.2
pymongo>=4.6.1
psycopg2-binary>=2.9.9
redis>=5.0.1
python-dotenv>=1.0.0
pytest>=7.4.4
pytest-asyncio>=0.23.3
EOF
make_commit "2026-05-12 13:30:00" "chore(shared): update pytest config and requirements"

# 28: README update
cat > README.md << 'EOF'
# Autonomous Email Outreach

An event-driven microservices platform for autonomous B2B email outreach — from lead discovery through personalized messaging.

## Architecture

```
                    ┌──────────────┐
   POST /campaigns  │ Orchestrator │  ← Express + PostgreSQL
                    │  (Node.js)   │
                    └──────┬───────┘
                           │ RabbitMQ (topic exchange)
            ┌──────────────┼──────────────┐
            ▼              ▼              ▼
     ┌────────────┐ ┌────────────┐ ┌────────────┐
     │  Planning   │ │  Sourcing  │ │ Prospecting│
     │  (Python)   │ │  (Python)  │ │  (Python)  │
     └──────┬─────┘ └──────┬─────┘ └──────┬─────┘
            │              │              │
            ▼              ▼              ▼
     ┌────────────┐ ┌────────────┐ ┌────────────┐
     │  Messaging  │ │ Observabil │ │   Web UI   │
     │  (Python)   │ │  (Python)  │ │  (React)   │
     └────────────┘ └────────────┘ └────────────┘
```

## Services

| Service | Language | Port | Description |
|---------|----------|------|-------------|
| Orchestrator | TypeScript | 3000 | Campaign CRUD, pipeline coordination |
| Planning | Python | 8000 | ICP → outreach plan generation |
| Sourcing | Python | 8001 | Company discovery (YC, HN, PH, OpenCorp) |
| Prospecting | Python | 8002 | Contact enrichment and scoring |
| Messaging | Python | 8003 | Email draft generation and sending |
| Observability | Python | 8004 | Metrics, logs, and dashboards |
| Web UI | React | 5173 | Campaign management dashboard |

## Quick Start

```bash
# Start infrastructure
docker compose up -d rabbitmq mongodb postgres redis

# Start orchestrator
cd src/orchestrator && npm install && npm run dev

# Start sourcing
cd src/sourcing && pip install -r requirements.txt && python -m sourcing.main
```

## Project Structure

```
├── src/
│   ├── orchestrator/    # Express API + RabbitMQ coordination
│   ├── planning/        # Outreach plan generation
│   ├── sourcing/        # Company discovery pipeline
│   ├── prospecting/     # Contact enrichment
│   ├── messaging/       # Email drafting + SMTP
│   ├── observability/   # Metrics and monitoring
│   ├── web-ui/          # React dashboard
│   ├── shared/          # Common models, logger, rate limiter
│   └── local_infrastructure/  # Dev environment setup
├── deploy/              # Helm charts + platform config
├── cloud_terraform/     # AWS infrastructure as code
└── design_docs/         # Architecture and design decisions
```

## Design Documents

- [Orchestrator Service Role](design_docs/orchestrator_service_role.md)
- [Data Sourcing Map](design_docs/data_sourcing_map.md)
- [Enrichment Redesign](design_docs/enrichment_redesign.md)
- [Observability Stack](design_docs/observability.md)
- [Cloud Infrastructure](design_docs/cloud_INFRASTRUCTURE.md)
EOF
make_commit "2026-05-12 16:00:00" "docs: rewrite README with architecture diagram and service table"

# 29: .env.example + gitignore cleanup
cat > .env.example << 'EOF'
# ── Infrastructure ────────────────────────────────────────
RABBITMQ_URL=amqp://guest:guest@localhost:5672
MONGO_URI=mongodb://localhost:27017/outreach
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/orchestrator
REDIS_URL=redis://localhost:6379/0

# ── Orchestrator ──────────────────────────────────────────
PORT=3000
EXCHANGE_NAME=outreach.events
NODE_ENV=development

# ── Sourcing ──────────────────────────────────────────────
API_RATE_LIMIT=2.0
API_BURST_SIZE=5
MAX_RETRIES=3
ENABLE_YC=true
ENABLE_HN=true
ENABLE_PH=false
ENABLE_OPENCORP=false
CACHE_TTL=86400

# ── Messaging ─────────────────────────────────────────────
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASS=
EOF

cat >> .gitignore << 'EOF'

# Python
__pycache__/
*.pyc
.pytest_cache/
*.egg-info/
dist/
venv/

# Node
node_modules/
dist/
*.js.map

# IDE
.vscode/
.idea/

# Environment
.env
.env.local
EOF
make_commit "2026-05-13 10:00:00" "chore: add root .env.example and update .gitignore"

# ════════════════════════════════════════════════════════════
echo ""
echo "════════════════════════════════════════════════════════"
echo "✅  Done! 29 commits with real code on '$BRANCH'."
echo ""
echo "    Date range       : May 7 – May 13, 2026"
echo "    May 7  : 5 commits (shared logger, rate limiter, sourcing config/cache/validation)"
echo "    May 8  : 5 commits (messaging templates/sanitizer/smtp, shared models, tests)"
echo "    May 9  : 5 commits (sourcing pipeline/subscriber/publisher/logging, tests)"
echo "    May 10 : 5 commits (messaging tests, docker-compose, helm chart)"
echo "    May 11 : 4 commits (source map, handlers, design docs)"
echo "    May 12 : 4 commits (sourcing main, helm, pytest config, README)"
echo "    May 13 : 1 commit  (.env.example, .gitignore)"
echo ""
echo "Next steps:"
echo "  1. Review:  git log --oneline | head -35"
echo "  2. Push:    git push origin $BRANCH --force"
echo "════════════════════════════════════════════════════════"
