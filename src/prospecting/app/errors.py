from __future__ import annotations


class ProspectingError(Exception):
    """Base error for prospecting message handling."""


class MalformedMessageError(ProspectingError):
    """Permanent failure for invalid or non-JSON prospecting.requested payloads."""


class PermanentProcessingError(ProspectingError):
    """Permanent failure for missing campaign/plan or invalid business state."""


class RetryableProcessingError(ProspectingError):
    """Transient failure that should be retried by RabbitMQ."""
