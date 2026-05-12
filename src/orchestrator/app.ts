import express from 'express';
import { createCampaignRouter, createReviewRouter, createHealthRouter } from './routes';
import { PipelineService, ReviewService } from './services';
import { errorHandler } from './middleware/error-handler';
import { MessageBroker } from '../local_infrastructure/rabbit_mq/broker.interface';

export function createApp(broker: MessageBroker): {
  app: express.Application;
  pipelineService: PipelineService;
  reviewService: ReviewService;
} {
  const app = express();

  // ── Middleware ──────────────────────────────────────────────
  app.use(express.json());

  // ── Services ───────────────────────────────────────────────
  const pipelineService = new PipelineService(broker);
  const reviewService = new ReviewService(broker);

  // ── Routes ─────────────────────────────────────────────────
  app.use('/campaigns', createCampaignRouter(pipelineService));
  app.use('/', createReviewRouter(reviewService));
  app.use('/', createHealthRouter());

  // ── Error Handler ──────────────────────────────────────────
  app.use(errorHandler);

  return { app, pipelineService, reviewService };
}
