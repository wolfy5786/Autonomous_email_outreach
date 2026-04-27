import dotenv from 'dotenv';
dotenv.config();

export const config = {
  port: parseInt(process.env.PORT || '3000', 10),
  rabbitmqUrl: process.env.RABBITMQ_URL || 'amqp://guest:guest@localhost:5672',
  mongoUri: process.env.MONGO_URI || 'mongodb://localhost:27017/outreach',
  postgresUrl: process.env.DATABASE_URL || 'postgresql://postgres:postgres@localhost:5432/orchestrator',
  exchange: process.env.EXCHANGE_NAME || 'outreach.events',
  nodeEnv: process.env.NODE_ENV || 'development',
};
