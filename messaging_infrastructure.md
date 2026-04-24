Problem we are using Amazon SQS for messaging queue for cloud infrastructure, and RabbitMQ for local development.

The classic solution here is the **strategy pattern** — you write your application code against an abstract messaging interface, then provide two concrete implementations: one for RabbitMQ (dev) and one for SQS (production). A dependency injection config switches between them at startup.

Here's the architecture, then the code.Your service only ever talks to the `MessageBroker` interface — it has zero knowledge of which broker is running underneath.

---

## The interfaceThe classic solution here is the **strategy pattern** — you write your application code against an abstract messaging interface, then provide two concrete implementations: one for RabbitMQ (dev) and one for SQS (production). A dependency injection config switches between them at startup.

Here's the architecture, then the code.Your service only ever talks to the `MessageBroker` interface — it has zero knowledge of which broker is running underneath.

---

## The interface

```typescript
// src/messaging/broker.interface.ts
export interface MessageBroker {
  publish(topic: string, message: unknown): Promise<void>;
  subscribe(topic: string, handler: (message: unknown) => Promise<void>): Promise<void>;
  disconnect(): Promise<void>;
}
```

---

## RabbitMQ adapter (dev)

```typescript
// src/messaging/rabbitmq.broker.ts
import amqp, { Connection, Channel } from 'amqplib';
import { MessageBroker } from './broker.interface';

export class RabbitMQBroker implements MessageBroker {
  private connection: Connection | null = null;
  private channel: Channel | null = null;

  constructor(private readonly url: string) {}

  private async getChannel(): Promise<Channel> {
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
      await handler(JSON.parse(msg.content.toString()));
      ch.ack(msg);
    });
  }

  async disconnect(): Promise<void> {
    await this.channel?.close();
    await this.connection?.close();
  }
}
```

---

## SQS adapter (prod)

```typescript
// src/messaging/sqs.broker.ts
import { SQSClient, SendMessageCommand, ReceiveMessageCommand, DeleteMessageCommand, CreateQueueCommand } from '@aws-sdk/client-sqs';
import { MessageBroker } from './broker.interface';

export class SQSBroker implements MessageBroker {
  private client: SQSClient;
  private queueUrls: Map<string, string> = new Map();

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
    await this.client.send(new SendMessageCommand({
      QueueUrl: queueUrl,
      MessageBody: JSON.stringify(message),
    }));
  }

  async subscribe(topic: string, handler: (msg: unknown) => Promise<void>): Promise<void> {
    const queueUrl = await this.getQueueUrl(topic);

    const poll = async () => {
      const result = await this.client.send(new ReceiveMessageCommand({
        QueueUrl: queueUrl,
        MaxNumberOfMessages: 10,
        WaitTimeSeconds: 20, // long polling — saves cost
      }));

      for (const msg of result.Messages ?? []) {
        await handler(JSON.parse(msg.Body!));
        await this.client.send(new DeleteMessageCommand({
          QueueUrl: queueUrl,
          ReceiptHandle: msg.ReceiptHandle!,
        }));
      }
      poll(); // keep polling
    };

    poll();
  }

  async disconnect(): Promise<void> {
    this.client.destroy();
  }
}
```

---

## The factory — the only place that reads the environment

```typescript
// src/messaging/broker.factory.ts
import { MessageBroker } from './broker.interface';
import { RabbitMQBroker } from './rabbitmq.broker';
import { SQSBroker } from './sqs.broker';

export function createBroker(): MessageBroker {
  const type = process.env.BROKER_TYPE ?? 'rabbitmq';

  switch (type) {
    case 'sqs':
      return new SQSBroker(process.env.AWS_REGION ?? 'us-east-1');
    case 'rabbitmq':
      return new RabbitMQBroker(process.env.RABBITMQ_URL ?? 'amqp://localhost');
    default:
      throw new Error(`Unknown BROKER_TYPE: "${type}"`);
  }
}
```

---

## Your service — completely broker-agnostic

```typescript
// src/order.service.ts
import { MessageBroker } from './messaging/broker.interface';

export class OrderService {
  constructor(private readonly broker: MessageBroker) {}

  async placeOrder(order: { id: string; amount: number }) {
    // business logic...
    await this.broker.publish('orders.created', order);
  }

  async startListening() {
    await this.broker.subscribe('orders.created', async (msg) => {
      console.log('Processing order:', msg);
    });
  }
}
```

## Wiring it all together

```typescript
// src/main.ts
import { createBroker } from './messaging/broker.factory';
import { OrderService } from './order.service';

const broker = createBroker(); // reads BROKER_TYPE
const service = new OrderService(broker);

await service.startListening();

// graceful shutdown
process.on('SIGTERM', () => broker.disconnect());
```

---

## Environment config

```bash
# .env.development
BROKER_TYPE=rabbitmq
RABBITMQ_URL=amqp://localhost

# .env.production
BROKER_TYPE=sqs
AWS_REGION=us-east-1
```

---

## Key design decisions to be aware of

**Message acknowledgement** behaves differently between the two. RabbitMQ uses `ch.ack(msg)` after processing; SQS uses `DeleteMessage`. The adapters above hide this difference entirely from your business logic.

**SQS doesn't have topics** — it uses queue URLs. The `getQueueUrl` helper maps your topic strings to SQS queue URLs so your publishing calls stay identical.

**Long polling** (`WaitTimeSeconds: 20`) is important in the SQS adapter — without it you'd hammer the API with empty responses and incur unnecessary cost.

**For NestJS or other DI frameworks**, register the broker as a provider token (`BROKER_TOKEN`) and inject it — the factory becomes a provider factory, but the rest of the pattern stays identical.

```typescript
// src/messaging/broker.interface.ts
export interface MessageBroker {
  publish(topic: string, message: unknown): Promise<void>;
  subscribe(topic: string, handler: (message: unknown) => Promise<void>): Promise<void>;
  disconnect(): Promise<void>;
}
```

---

## RabbitMQ adapter (dev)

```typescript
// src/messaging/rabbitmq.broker.ts
import amqp, { Connection, Channel } from 'amqplib';
import { MessageBroker } from './broker.interface';

export class RabbitMQBroker implements MessageBroker {
  private connection: Connection | null = null;
  private channel: Channel | null = null;

  constructor(private readonly url: string) {}

  private async getChannel(): Promise<Channel> {
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
      await handler(JSON.parse(msg.content.toString()));
      ch.ack(msg);
    });
  }

  async disconnect(): Promise<void> {
    await this.channel?.close();
    await this.connection?.close();
  }
}
```

---

## SQS adapter (prod)

```typescript
// src/messaging/sqs.broker.ts
import { SQSClient, SendMessageCommand, ReceiveMessageCommand, DeleteMessageCommand, CreateQueueCommand } from '@aws-sdk/client-sqs';
import { MessageBroker } from './broker.interface';

export class SQSBroker implements MessageBroker {
  private client: SQSClient;
  private queueUrls: Map<string, string> = new Map();

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
    await this.client.send(new SendMessageCommand({
      QueueUrl: queueUrl,
      MessageBody: JSON.stringify(message),
    }));
  }

  async subscribe(topic: string, handler: (msg: unknown) => Promise<void>): Promise<void> {
    const queueUrl = await this.getQueueUrl(topic);

    const poll = async () => {
      const result = await this.client.send(new ReceiveMessageCommand({
        QueueUrl: queueUrl,
        MaxNumberOfMessages: 10,
        WaitTimeSeconds: 20, // long polling — saves cost
      }));

      for (const msg of result.Messages ?? []) {
        await handler(JSON.parse(msg.Body!));
        await this.client.send(new DeleteMessageCommand({
          QueueUrl: queueUrl,
          ReceiptHandle: msg.ReceiptHandle!,
        }));
      }
      poll(); // keep polling
    };

    poll();
  }

  async disconnect(): Promise<void> {
    this.client.destroy();
  }
}
```

---

## The factory — the only place that reads the environment

```typescript
// src/messaging/broker.factory.ts
import { MessageBroker } from './broker.interface';
import { RabbitMQBroker } from './rabbitmq.broker';
import { SQSBroker } from './sqs.broker';

export function createBroker(): MessageBroker {
  const type = process.env.BROKER_TYPE ?? 'rabbitmq';

  switch (type) {
    case 'sqs':
      return new SQSBroker(process.env.AWS_REGION ?? 'us-east-1');
    case 'rabbitmq':
      return new RabbitMQBroker(process.env.RABBITMQ_URL ?? 'amqp://localhost');
    default:
      throw new Error(`Unknown BROKER_TYPE: "${type}"`);
  }
}
```

---

## Your service — completely broker-agnostic

```typescript
// src/order.service.ts
import { MessageBroker } from './messaging/broker.interface';

export class OrderService {
  constructor(private readonly broker: MessageBroker) {}

  async placeOrder(order: { id: string; amount: number }) {
    // business logic...
    await this.broker.publish('orders.created', order);
  }

  async startListening() {
    await this.broker.subscribe('orders.created', async (msg) => {
      console.log('Processing order:', msg);
    });
  }
}
```

## Wiring it all together

```typescript
// src/main.ts
import { createBroker } from './messaging/broker.factory';
import { OrderService } from './order.service';

const broker = createBroker(); // reads BROKER_TYPE
const service = new OrderService(broker);

await service.startListening();

// graceful shutdown
process.on('SIGTERM', () => broker.disconnect());
```

---

## Environment config

```bash
# .env.development
BROKER_TYPE=rabbitmq
RABBITMQ_URL=amqp://localhost

# .env.production
BROKER_TYPE=sqs
AWS_REGION=us-east-1
```

---

## Key design decisions to be aware of

**Message acknowledgement** behaves differently between the two. RabbitMQ uses `ch.ack(msg)` after processing; SQS uses `DeleteMessage`. The adapters above hide this difference entirely from your business logic.

**SQS doesn't have topics** — it uses queue URLs. The `getQueueUrl` helper maps your topic strings to SQS queue URLs so your publishing calls stay identical.

**Long polling** (`WaitTimeSeconds: 20`) is important in the SQS adapter — without it you'd hammer the API with empty responses and incur unnecessary cost.

**For NestJS or other DI frameworks**, register the broker as a provider token (`BROKER_TOKEN`) and inject it — the factory becomes a provider factory, but the rest of the pattern stays identical.