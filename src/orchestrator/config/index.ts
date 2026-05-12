import dotenv from 'dotenv';
dotenv.config();

export const config = {
  port: parseInt(process.env.PORT ?? '3000', 10),
  mongoUri: process.env.MONGO_URI ?? 'mongodb://localhost:27017/email_outreach',
  rabbitmqUrl:
    process.env.RABBITMQ_URL ?? 'amqp://guest:guest@localhost:5672/',
  retryLimit: parseInt(process.env.RETRY_LIMIT ?? '3', 10),
  logLevel: process.env.LOG_LEVEL ?? 'info',
} as const;
