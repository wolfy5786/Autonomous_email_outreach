import { Router } from 'express';
import { CampaignStatusRepository } from '../postgres';
import { getMetrics } from '../middleware/metrics';

export function createApiMetricsRouter(statusRepo: CampaignStatusRepository): Router {
  const router = Router();

  // GET /api/metrics — internal metrics endpoint
  router.get('/metrics', (_req, res) => {
    res.json(getMetrics());
  });

  return router;
}
