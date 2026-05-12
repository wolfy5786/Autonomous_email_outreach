import os

from .broker_interface import MessageBroker
from .traced_broker import TracedBroker


def create_broker() -> MessageBroker:
    """Return a MessageBroker based on the BROKER_TYPE env var.

    The returned broker is always wrapped in a :class:`TracedBroker` so every
    publish/consume produces trace events and propagates trace context. The
    actual wire-level adapter (currently only ``rabbitmq``) is selected by
    ``BROKER_TYPE``. Service name is taken from ``SERVICE_NAME`` (defaults to
    ``unknown``) and stamped on every trace event.
    """
    broker_type = os.getenv("BROKER_TYPE", "rabbitmq").lower()

    if broker_type == "rabbitmq":
        from local_infrastructure.factory.rabbitmq_broker import RabbitMQBroker

        inner: MessageBroker = RabbitMQBroker(
            url=os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/"),
            prefetch=int(os.getenv("RABBIT_PREFETCH", "10")),
        )
    else:
        raise ValueError(f"Unknown BROKER_TYPE: {broker_type!r}. Expected 'rabbitmq'.")

    service = os.getenv("SERVICE_NAME", "unknown")
    return TracedBroker(inner, service=service)
