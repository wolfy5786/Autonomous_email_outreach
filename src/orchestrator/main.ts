import mongoose from 'mongoose';
import { config } from './config';
import { createApp } from './app';
import { createBroker } from '../local_infrastructure/factory/broker.factory';

async function main(): Promise<void> {
  // ── Connect to MongoDB ─────────────────────────────────────
  console.log(`[main] Connecting to MongoDB at ${config.mongoUri}…`);
  await mongoose.connect(config.mongoUri);
  console.log('[main] MongoDB connected.');

  // ── Create message broker ──────────────────────────────────
  const broker = createBroker();
  console.log(`[main] Broker type: ${config.brokerType}`);

  // ── Build Express app ──────────────────────────────────────
  const { app, pipelineService, reviewService } = createApp(broker);

  // ── Start queue listeners ──────────────────────────────────
  await pipelineService.startListening();
  await reviewService.startListening();

  // ── Start HTTP server ──────────────────────────────────────
  app.listen(config.port, () => {
    console.log(`[main] Orchestrator listening on :${config.port}`);
    console.log(`[main] Endpoints:`);
    console.log(`       POST   /campaigns              — Create campaign`);
    console.log(`       GET    /campaigns              — List campaigns`);
    console.log(`       GET    /campaigns/:id          — Campaign details`);
    console.log(`       PATCH  /campaigns/:id          — Pause/resume`);
    console.log(`       DELETE /campaigns/:id          — Cancel campaign`);
    console.log(`       GET    /campaigns/:id/stats    — Campaign stats`);
    console.log(`       GET    /campaigns/:id/prospects— List prospects`);
    console.log(`       GET    /campaigns/:id/drafts   — List drafts`);
    console.log(`       GET    /drafts/:id             — Get draft`);
    console.log(`       PATCH  /drafts/:id             — Edit draft`);
    console.log(`       POST   /drafts/:id/approve     — Approve draft`);
    console.log(`       POST   /drafts/:id/reject      — Reject draft`);
    console.log(`       POST   /drafts/:id/regenerate  — Regenerate draft`);
    console.log(`       GET    /review/queue            — Review queue`);
    console.log(`       POST   /review/bulk-approve     — Bulk approve`);
    console.log(`       GET    /health                  — Liveness`);
    console.log(`       GET    /status                  — System status`);
  });

  // ── Graceful shutdown ──────────────────────────────────────
  const shutdown = async (signal: string) => {
    console.log(`\n[main] Received ${signal}. Shutting down…`);
    await broker.disconnect();
    await mongoose.disconnect();
    process.exit(0);
  };

  process.on('SIGTERM', () => shutdown('SIGTERM'));
  process.on('SIGINT', () => shutdown('SIGINT'));
}

main().catch((err) => {
  console.error('[main] Fatal error:', err);
  process.exit(1);
});
