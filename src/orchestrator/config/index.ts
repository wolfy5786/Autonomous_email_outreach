import dotenv from 'dotenv';
dotenv.config();

export const config = {
  port: parseInt(process.env.PORT ?? '3000', 10),
  mongoUri: process.env.MONGO_URI ?? 'mongodb://localhost:27017/email_outreach',
  rabbitmqUrl:
    process.env.RABBITMQ_URL ?? 'amqp://guest:guest@localhost:5672/',
  // PostgreSQL — per-campaign orchestration status (orchestrator_service_role.md §2.1).
  postgresUrl:
    process.env.POSTGRES_URL ??
    'postgres://orchestrator:orchestrator@localhost:5432/email_outreach',
  retryLimit: parseInt(process.env.RETRY_LIMIT ?? '3', 10),
  logLevel: process.env.LOG_LEVEL ?? 'info',
  // Cosmetic gap between prospecting.completed and messaging.requested so
  // the prospecting stage is visible on the campaign timeline (default 2s).
  prospectingDelayMs: parseInt(process.env.PROSPECTING_DELAY_MS ?? '2000', 10),
} as const;
