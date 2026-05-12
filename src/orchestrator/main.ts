import mongoose from 'mongoose';
import { config } from './config';
import { createApp } from './app';
import { EventsBroker } from './rabbit/events-broker';
import { CampaignStatusRepository, PostgresClient } from './postgres';

async function main(): Promise<void> {
  // ── Connect to MongoDB ─────────────────────────────────────
  console.log(`[main] Connecting to MongoDB at ${config.mongoUri}…`);
  await mongoose.connect(config.mongoUri);
  console.log('[main] MongoDB connected.');

  // ── Connect to PostgreSQL (campaign status — §2.1) ─────────
  console.log(`[main] Connecting to PostgreSQL at ${config.postgresUrl}…`);
  const pg = new PostgresClient(config.postgresUrl);
  await pg.connect();
  const statusRepo = new CampaignStatusRepository(pg);
  await statusRepo.ensureSchema();
  console.log('[main] PostgreSQL connected; campaign_status schema ready.');

  // ── Create message broker ──────────────────────────────────
  const broker = new EventsBroker(config.rabbitmqUrl);
  console.log('[main] EventsBroker (RabbitMQ topic exchange) ready.');

  // ── Build Express app ──────────────────────────────────────
  const { app, pipelineService } = createApp(broker, statusRepo);

  // ── Start queue listeners ──────────────────────────────────
  await pipelineService.startListening();

  // ── Start HTTP server ──────────────────────────────────────
  app.listen(config.port, () => {
    console.log(`[main] Orchestrator listening on :${config.port}`);
    console.log(`[main] Endpoints (see design_docs/orchestrator_service_role.md section 3):`);
    console.log(`       POST   /api/campaigns                 — Create campaign`);
    console.log(`       GET    /api/campaigns                 — List campaigns`);
    console.log(`       GET    /api/campaigns/:id            — Campaign details`);
    console.log(`       PATCH  /api/campaigns/:id            — Pause/resume`);
    console.log(`       DELETE /api/campaigns/:id            — Cancel campaign`);
    console.log(`       GET    /api/campaigns/:id/stats      — Campaign stats`);
    console.log(`       GET    /api/campaigns/:id/prospects — List prospects`);
    console.log(`       GET    /api/campaigns/:id/drafts    — List drafts`);
    console.log(`       GET    /api/prospects/:id           — Prospect detail (stub)`);
    console.log(`       GET    /api/drafts/:id               — Draft by id`);
    console.log(`       GET    /api/status                    — System status`);
    console.log(`       GET    /health                        — Liveness`);
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
