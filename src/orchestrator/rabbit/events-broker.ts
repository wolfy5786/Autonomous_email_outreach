import amqp from 'amqplib';
import { MessageBroker } from '../../local_infrastructure/rabbit_mq/broker.interface';

const DEFAULT_EXCHANGE = 'email_outreach.events';

/**
 * Publishes to the topic exchange with routing key = queue/event name (see definitions.json).
 * Consumes from pre-declared queues (topology loaded by RabbitMQ Docker definitions).
 */
export class EventsBroker implements MessageBroker {
  private connection: amqp.ChannelModel | null = null;
  private publishChannel: amqp.Channel | null = null;
  private consumeChannel: amqp.Channel | null = null;

  constructor(
    private readonly url: string,
    private readonly exchangeName: string = process.env.RABBITMQ_EXCHANGE ?? DEFAULT_EXCHANGE
  ) {}

  private async getConnection(): Promise<amqp.ChannelModel> {
    if (!this.connection) {
      this.connection = await amqp.connect(this.url);
    }
    return this.connection;
  }

  async publish(topic: string, message: unknown): Promise<void> {
    const conn = await this.getConnection();
    if (!this.publishChannel) {
      this.publishChannel = await conn.createChannel();
      await this.publishChannel.assertExchange(this.exchangeName, 'topic', { durable: true });
    }
    const body = Buffer.from(JSON.stringify(message));
    this.publishChannel.publish(this.exchangeName, topic, body, { persistent: true });
  }

  async subscribe(queueName: string, handler: (msg: unknown) => Promise<void>): Promise<void> {
    const conn = await this.getConnection();
    if (!this.consumeChannel) {
      this.consumeChannel = await conn.createChannel();
      await this.consumeChannel.prefetch(1);
    }
    const ch = this.consumeChannel;
    await ch.consume(queueName, async (msg) => {
      if (!msg) return;
      try {
        await handler(JSON.parse(msg.content.toString()));
        ch.ack(msg);
      } catch (err) {
        console.error(`[EventsBroker] Error processing ${queueName}:`, err);
        ch.nack(msg, false, true);
      }
    });
  }

  async disconnect(): Promise<void> {
    await this.publishChannel?.close();
    await this.consumeChannel?.close();
    this.publishChannel = null;
    this.consumeChannel = null;
    await this.connection?.close();
    this.connection = null;
  }
}
