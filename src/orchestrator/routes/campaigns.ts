import { Router, Request, Response, NextFunction } from 'express';
import { StatsAggregator } from '../services/statsAggregator';

export function createCampaignStatsRouter(): Router {
  const router = Router();
  const statsAggregator = new StatsAggregator();

  // GET /api/campaigns/:id/stats
  router.get('/:id/stats', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const stats = await statsAggregator.getCampaignStats(req.params.id);
      res.json(stats);
    } catch (err) {
      next(err);
    }
  });

  return router;
}
