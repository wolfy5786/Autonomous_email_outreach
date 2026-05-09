import express from 'express';
import {
  createCampaignRouter,
  createHealthRouter,
  createApiRouter,
  createProspectsRouter,
  createDraftsRouter,
  createCampaignStatsRouter,
} from './routes';
import { PipelineService } from './services';
import { errorHandler } from './middleware/error-handler';
import { requestLogger } from './middleware/requestLogger';
import { metricsMiddleware } from './middleware/metrics';
import { MessageBroker } from '../local_infrastructure/rabbit_mq/broker.interface';
import { CampaignStatusRepository } from './postgres';

export function createApp(
  broker: MessageBroker,
  statusRepo: CampaignStatusRepository
): {
  app: express.Application;
  pipelineService: PipelineService;
} {
  const app = express();

  // ── Global Middleware ──────────────────────────────────────
  app.use(express.json());
  app.use(requestLogger);
  app.use(metricsMiddleware);

  // ── Services ───────────────────────────────────────────────
  const pipelineService = new PipelineService(broker, statusRepo);

  // ── Routes ─────────────────────────────────────────────────
  app.use('/api/campaigns', createCampaignRouter(pipelineService, statusRepo));
  app.use('/api/campaigns', createCampaignStatsRouter());
  app.use('/api', createApiRouter(statusRepo));
  app.use('/api', createProspectsRouter());
  app.use('/api', createDraftsRouter());
  app.use('/', createHealthRouter());

  // ── Error Handler ──────────────────────────────────────────
  app.use(errorHandler);

  return { app, pipelineService };
}
