import mongoose from 'mongoose';
import { config } from './config';
import { createApp } from './app';
import { EventsBroker } from './rabbit/events-broker';
import { CampaignStatusRepository, PostgresClient } from './postgres';
import { AuditLog } from './postgres/auditLog';

async function main(): Promise<void> {
  // ── Connect to MongoDB ─────────────────────────────────────
  console.log(`[main] Connecting to MongoDB at ${config.mongoUri}…`);
  await mongoose.connect(config.mongoUri);
  console.log('[main] MongoDB connected.');

  // ── Connect to PostgreSQL ──────────────────────────────────
  console.log(`[main] Connecting to PostgreSQL at ${config.postgresUrl}…`);
  const pg = new PostgresClient(config.postgresUrl);
  await pg.connect();

  const statusRepo = new CampaignStatusRepository(pg);
  await statusRepo.ensureSchema();

  const auditLog = new AuditLog(pg);
  await auditLog.ensureSchema();

  console.log('[main] PostgreSQL connected; schemas ready.');

  // ── Create message broker ──────────────────────────────────
  const broker = new EventsBroker(config.rabbitmqUrl);
  console.log('[main] EventsBroker ready.');

  // ── Build Express app ──────────────────────────────────────
  const { app, pipelineService } = createApp(broker, statusRepo);

  // ── Start queue listeners ──────────────────────────────────
  await pipelineService.startListening();

  // ── Start HTTP server ──────────────────────────────────────
  app.listen(config.port, () => {
    console.log(`[main] Orchestrator listening on :${config.port}`);
  });

  // ── Graceful shutdown ──────────────────────────────────────
  const shutdown = async (signal: string) => {
    console.log(`\n[main] Received ${signal}. Shutting down…`);
    await broker.disconnect();
    await mongoose.disconnect();
    await pg.disconnect();
    process.exit(0);
  };

  process.on('SIGTERM', () => shutdown('SIGTERM'));
  process.on('SIGINT', () => shutdown('SIGINT'));
}

main().catch((err) => {
  console.error('[main] Fatal error:', err);
  process.exit(1);
});
