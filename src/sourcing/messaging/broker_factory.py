"""Factory for broker implementations based on configuration."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from messaging.broker_interface import BrokerInterface
from messaging.rabbitmq_broker import RabbitmqBroker

_SOURCING_ROOT = Path(__file__).resolve().parent.parent


def create_broker() -> BrokerInterface:
    """Return a broker instance for ``BROKER_TYPE`` (default: ``rabbitmq``)."""
    # Local runs: load src/sourcing/.env so RABBITMQ_URL etc. match Docker env_file behavior.
    load_dotenv(_SOURCING_ROOT / ".env", override=False)

    broker_type = os.environ.get("BROKER_TYPE", "rabbitmq").strip().lower()
    if broker_type == "rabbitmq":
        return RabbitmqBroker()
    raise ValueError(f"Unsupported BROKER_TYPE: {broker_type!r}. Use 'rabbitmq'.")
