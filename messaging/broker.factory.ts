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
