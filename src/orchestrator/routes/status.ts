import { Router, Request, Response, NextFunction } from 'express';
import { CampaignStatusRepository } from '../postgres';

export function createStatusRouter(statusRepo: CampaignStatusRepository): Router {
  const router = Router();

  // GET /api/status — system health + queue depths
  router.get('/status', async (_req: Request, res: Response, next: NextFunction) => {
    try {
      const campaigns = await statusRepo.findAll(1000, 0);

      const statusCounts: Record<string, number> = {};
      for (const c of campaigns) {
        statusCounts[c.status] = (statusCounts[c.status] || 0) + 1;
      }

      res.json({
        service: 'orchestrator',
        status: 'operational',
        totalCampaigns: campaigns.length,
        byStatus: statusCounts,
        timestamp: new Date().toISOString(),
      });
    } catch (err) {
      next(err);
    }
  });

  return router;
}
