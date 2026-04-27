"""Factory for broker implementations based on configuration."""

from __future__ import annotations

import os

from messaging.broker_interface import BrokerInterface
from messaging.rabbitmq_broker import RabbitmqBroker


def create_broker() -> BrokerInterface:
    """Return a broker instance for ``BROKER_TYPE`` (default: ``rabbitmq``)."""
    broker_type = os.environ.get("BROKER_TYPE", "rabbitmq").strip().lower()
    if broker_type == "rabbitmq":
        return RabbitmqBroker()
    raise ValueError(f"Unsupported BROKER_TYPE: {broker_type!r}. Use 'rabbitmq'.")
