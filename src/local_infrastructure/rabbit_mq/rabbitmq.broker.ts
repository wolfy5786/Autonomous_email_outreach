import amqp from 'amqplib';
import { MessageBroker } from './broker.interface';

export class RabbitMQBroker implements MessageBroker {
  private connection: amqp.ChannelModel | null = null;
  private channel: amqp.Channel | null = null;

  constructor(private readonly url: string) {}

  private async getChannel(): Promise<amqp.Channel> {
    if (!this.channel) {
      this.connection = await amqp.connect(this.url);
      this.channel = await this.connection.createChannel();
    }
    return this.channel;
  }

  async publish(topic: string, message: unknown): Promise<void> {
    const ch = await this.getChannel();
    await ch.assertQueue(topic, { durable: true });
    ch.sendToQueue(topic, Buffer.from(JSON.stringify(message)), { persistent: true });
  }

  async subscribe(topic: string, handler: (msg: unknown) => Promise<void>): Promise<void> {
    const ch = await this.getChannel();
    await ch.assertQueue(topic, { durable: true });
    ch.consume(topic, async (msg) => {
      if (!msg) return;
      try {
        await handler(JSON.parse(msg.content.toString()));
        ch.ack(msg);
      } catch (err) {
        console.error(`[RabbitMQBroker] Error processing message on ${topic}:`, err);
        ch.nack(msg, false, true);
      }
    });
  }

  async disconnect(): Promise<void> {
    await this.channel?.close();
    await this.connection?.close();
  }
}
