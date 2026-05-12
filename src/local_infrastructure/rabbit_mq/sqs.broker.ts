import {
  SQSClient,
  SendMessageCommand,
  ReceiveMessageCommand,
  DeleteMessageCommand,
  CreateQueueCommand,
} from '@aws-sdk/client-sqs';
import { MessageBroker } from './broker.interface';

export class SQSBroker implements MessageBroker {
  private client: SQSClient;
  private queueUrls: Map<string, string> = new Map();
  private polling = true;

  constructor(region: string) {
    this.client = new SQSClient({ region });
  }

  private async getQueueUrl(topic: string): Promise<string> {
    if (this.queueUrls.has(topic)) return this.queueUrls.get(topic)!;

    const result = await this.client.send(new CreateQueueCommand({ QueueName: topic }));
    this.queueUrls.set(topic, result.QueueUrl!);
    return result.QueueUrl!;
  }

  async publish(topic: string, message: unknown): Promise<void> {
    const queueUrl = await this.getQueueUrl(topic);
    await this.client.send(
      new SendMessageCommand({
        QueueUrl: queueUrl,
        MessageBody: JSON.stringify(message),
      })
    );
  }

  async subscribe(topic: string, handler: (msg: unknown) => Promise<void>): Promise<void> {
    const queueUrl = await this.getQueueUrl(topic);

    const poll = async () => {
      while (this.polling) {
        try {
          const result = await this.client.send(
            new ReceiveMessageCommand({
              QueueUrl: queueUrl,
              MaxNumberOfMessages: 10,
              WaitTimeSeconds: 20,
            })
          );

          for (const msg of result.Messages ?? []) {
            try {
              await handler(JSON.parse(msg.Body!));
              await this.client.send(
                new DeleteMessageCommand({
                  QueueUrl: queueUrl,
                  ReceiptHandle: msg.ReceiptHandle!,
                })
              );
            } catch (err) {
              console.error(`[SQSBroker] Error processing message on ${topic}:`, err);
              // Message will become visible again after visibility timeout
            }
          }
        } catch (err) {
          console.error(`[SQSBroker] Polling error on ${topic}:`, err);
          // Back off before retrying
          await new Promise((r) => setTimeout(r, 5000));
        }
      }
    };

    poll();
  }

  async disconnect(): Promise<void> {
    this.polling = false;
    this.client.destroy();
  }
}
