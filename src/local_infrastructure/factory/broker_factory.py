import os

from .broker_interface import MessageBroker


def create_broker() -> MessageBroker:
    """Return a MessageBroker based on the BROKER_TYPE env var.

    Only `rabbitmq` is supported — production runs RabbitMQ in-cluster or via
    Amazon MQ for RabbitMQ. The factory is kept so additional brokers can be
    plugged in later without touching service code.
    """
    broker_type = os.getenv("BROKER_TYPE", "rabbitmq").lower()

    if broker_type == "rabbitmq":
        from local_infrastructure.factory.rabbitmq_broker import RabbitMQBroker

        return RabbitMQBroker(
            url=os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/"),
            prefetch=int(os.getenv("RABBIT_PREFETCH", "10")),
        )

    raise ValueError(f"Unknown BROKER_TYPE: {broker_type!r}. Expected 'rabbitmq'.")
