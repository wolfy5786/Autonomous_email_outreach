import os

from .broker_interface import MessageBroker


def create_broker() -> MessageBroker:
    """Return a MessageBroker based on the BROKER_TYPE env var.

    Imports are lazy so picking one broker doesn't force the other's deps.
    """
    broker_type = os.getenv("BROKER_TYPE", "rabbitmq").lower()

    if broker_type == "rabbitmq":
        from local_infrastructure.rabbit_mq.rabbitmq_broker import RabbitMQBroker

        return RabbitMQBroker(
            url=os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/"),
            prefetch=int(os.getenv("RABBIT_PREFETCH", "10")),
        )

    if broker_type == "sqs":
        from local_infrastructure.sqs.sqs_broker import SQSBroker

        return SQSBroker(region=os.getenv("AWS_REGION", "us-west-2"))

    raise ValueError(f"Unknown BROKER_TYPE: {broker_type!r}. Expected 'rabbitmq' or 'sqs'.")
