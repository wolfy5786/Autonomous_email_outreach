"""No-op broker for skeleton development."""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from .broker_interface import MessageBroker

MessageHandler = Callable[[dict[str, Any]], Awaitable[None]]


class NoopBroker(MessageBroker):
    def __init__(self, logger: logging.LoggerAdapter):
        self.logger = logger

    async def publish(self, topic: str, message: dict[str, Any]) -> None:
        self.logger.info(
            "broker=noop action=publish topic=%s payload_keys=%s",
            topic,
            sorted(message.keys()),
        )

    async def subscribe(self, topic: str, handler: MessageHandler) -> None:
        self.logger.info(
            "broker=noop action=subscribe topic=%s status=registered_handler_only",
            topic,
        )
        # Intentionally no message consumption in skeleton mode.
        _ = handler

    async def disconnect(self) -> None:
        self.logger.info("broker=noop action=disconnect status=ok")

