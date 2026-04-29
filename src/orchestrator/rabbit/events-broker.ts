import { Connection, Channel } from 'amqplib';
import { createConnection, createChannel } from './connection';
import { MessageBroker } from '../../local_infrastructure/rabbit_mq/broker.interface';

const EXCHANGE = 'outreach.events';
const EXCHANGE_TYPE = 'topic';

export class EventsBroker implements MessageBroker {
  private connection!: Connection;
  private channel!: Channel;

  constructor(private url: string) {}

  async init(): Promise<void> {
    this.connection = await createConnection(this.url);
    this.channel = await createChannel(this.connection);
    await this.channel.assertExchange(EXCHANGE, EXCHANGE_TYPE, { durable: true });
    console.log(`[EventsBroker] Exchange '${EXCHANGE}' (${EXCHANGE_TYPE}) asserted`);
  }

  async publish(routingKey: string, payload: unknown): Promise<void> {
    const message = Buffer.from(JSON.stringify({
      eventType: routingKey,
      payload,
      timestamp: new Date().toISOString(),
    }));

    this.channel.publish(EXCHANGE, routingKey, message, {
      persistent: true,
      contentType: 'application/json',
    });

    console.log(`[EventsBroker] Published ${routingKey}`);
  }

  async subscribe(routingKey: string, queue: string, handler: (msg: any) => Promise<void>): Promise<void> {
    await this.channel.assertQueue(queue, { durable: true });
    await this.channel.bindQueue(queue, EXCHANGE, routingKey);

    this.channel.consume(queue, async (msg) => {
      if (!msg) return;
      try {
        const parsed = JSON.parse(msg.content.toString());
        await handler(parsed);
        this.channel.ack(msg);
      } catch (err: any) {
        console.error(`[EventsBroker] Handler error on ${routingKey}:`, err.message);
        this.channel.nack(msg, false, false);
      }
    });

    console.log(`[EventsBroker] Subscribed to ${routingKey} via queue '${queue}'`);
  }

  async disconnect(): Promise<void> {
    await this.channel?.close();
    await this.connection?.close();
    console.log('[EventsBroker] Disconnected');
  }
}
