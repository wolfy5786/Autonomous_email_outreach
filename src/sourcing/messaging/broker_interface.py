"""Broker interface used by the sourcing service."""

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import Any

MessageHandler = Callable[[dict[str, Any]], Awaitable[None]]


class MessageBroker(ABC):
    @abstractmethod
    async def publish(self, topic: str, message: dict[str, Any]) -> None:
        """Publish a message to a topic."""

    @abstractmethod
    async def subscribe(self, topic: str, handler: MessageHandler) -> None:
        """Subscribe to a topic with an async handler."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Release broker resources."""

