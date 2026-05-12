import express from 'express';
import { createApiRouter, createCampaignRouter, createHealthRouter } from './routes';
import { PipelineService } from './services';
import { errorHandler } from './middleware/error-handler';
import { MessageBroker } from '../local_infrastructure/rabbit_mq/broker.interface';

export function createApp(broker: MessageBroker): {
  app: express.Application;
  pipelineService: PipelineService;
} {
  const app = express();

  // ── Middleware ──────────────────────────────────────────────
  app.use(express.json());

  // ── Services ───────────────────────────────────────────────
  const pipelineService = new PipelineService(broker);

  // ── Routes (canonical prefix /api/* — orchestrator_service_role.md §3) ──
  app.use('/api/campaigns', createCampaignRouter(pipelineService));
  app.use('/api', createApiRouter());
  app.use('/', createHealthRouter());

  // ── Error Handler ──────────────────────────────────────────
  app.use(errorHandler);

  return { app, pipelineService };
}
