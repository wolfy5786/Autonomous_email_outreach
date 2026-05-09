import dotenv from 'dotenv';
dotenv.config();

export const config = {
  port: parseInt(process.env.PORT ?? '3000', 10),
  mongoUri: process.env.MONGO_URI ?? 'mongodb://localhost:27017/email_outreach',
  brokerType: (process.env.BROKER_TYPE ?? 'rabbitmq') as 'rabbitmq' | 'sqs',
  rabbitmqUrl: process.env.RABBITMQ_URL ?? 'amqp://localhost',
  awsRegion: process.env.AWS_REGION ?? 'us-east-1',
  retryLimit: parseInt(process.env.RETRY_LIMIT ?? '3', 10),
  logLevel: process.env.LOG_LEVEL ?? 'info',
} as const;
