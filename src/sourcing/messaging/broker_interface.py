"""Abstract message broker contract for the sourcing service."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable

# Consumer callback: raw message body (bytes).
MessageCallback = Callable[[bytes], None]


class BrokerInterface(ABC):
    """Pluggable broker so the service can swap implementations (e.g. RabbitMQ, Amazon MQ)."""

    @abstractmethod
    def connect(self) -> None:
        """Establish connection to the broker."""
        raise NotImplementedError

    @abstractmethod
    def subscribe(self, queue: str, callback: MessageCallback) -> None:
        """Block and consume messages from *queue* until stopped or an error occurs."""
        raise NotImplementedError

    @abstractmethod
    def publish(self, exchange: str, routing_key: str, body: bytes) -> None:
        """Publish a message to the broker."""
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        """Release broker resources and close connections."""
        raise NotImplementedError

    def request_stop(self) -> None:
        """If ``subscribe`` is blocking, request it to return (e.g. signal handler). Default: no-op."""
        return
