from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import Any

MessageHandler = Callable[[dict[str, Any]], Awaitable[None]]


class NonRetryableError(Exception):
    """Raise from a handler when the message must NOT be redelivered.

    The broker adapter will reject it straight to the DLQ instead of requeueing.
    Use this for things like "campaign not found" — redelivery won't help.
    """


class MessageBroker(ABC):
    """Strategy-pattern interface for pub/sub over a message broker.

    Implementations exist for RabbitMQ (local dev) and SQS (production).
    Application code only ever sees this interface — the factory picks the
    concrete implementation from the `BROKER_TYPE` env var at startup.
    """

    @abstractmethod
    async def publish(self, topic: str, message: dict[str, Any]) -> None:
        """Publish a JSON-serialisable dict to the named topic/queue."""

    @abstractmethod
    async def subscribe(self, topic: str, handler: MessageHandler) -> None:
        """Start consuming the named topic. Returns immediately — consumer runs in the background."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Stop consumers, close connections. Idempotent."""
