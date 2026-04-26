from typing import Any

from local_infrastructure.factory.broker_interface import MessageBroker, MessageHandler

# TODO: implement for cloud deployment — see cloud_INFRASTRUCTURE.md §14 "Message Queue (Amazon SQS)".
# Production SQS adapter needs:
#   - aioboto3 SQSClient
#   - topic -> queue URL mapping (either pre-provisioned via Terraform or CreateQueue at boot)
#   - long polling (WaitTimeSeconds=20) to avoid empty-receive cost
#   - DeleteMessage as the ack primitive
#   - visibility timeouts per queue (see the table in cloud_INFRASTRUCTURE.md §14)
#   - IRSA-backed credentials (no static keys)


class SQSBroker(MessageBroker):
    """SQS adapter — stubbed. Implement before cloud deployment."""

    def __init__(self, region: str) -> None:
        self._region = region

    async def publish(self, topic: str, message: dict[str, Any]) -> None:
        raise NotImplementedError("SQS adapter not implemented — see cloud_INFRASTRUCTURE.md")

    async def subscribe(self, topic: str, handler: MessageHandler) -> None:
        raise NotImplementedError("SQS adapter not implemented — see cloud_INFRASTRUCTURE.md")

    async def disconnect(self) -> None:
        raise NotImplementedError("SQS adapter not implemented — see cloud_INFRASTRUCTURE.md")
