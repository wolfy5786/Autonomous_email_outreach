import { Router, Request, Response } from 'express';
import { Campaign } from '../../shared/models';

export function createHealthRouter(): Router {
  const router = Router();

  // GET /health — Service liveness check
  router.get('/health', (_req: Request, res: Response) => {
    res.json({ status: 'ok', service: 'orchestrator', timestamp: new Date().toISOString() });
  });

  // GET /status — Queue depths, service statuses, DLQ count
  router.get('/status', async (_req: Request, res: Response) => {
    try {
      const running = await Campaign.countDocuments({ status: 'running' });
      const review = await Campaign.countDocuments({ status: 'review' });
      const completed = await Campaign.countDocuments({ status: 'completed' });
      const paused = await Campaign.countDocuments({ status: 'paused' });

      res.json({
        service: 'orchestrator',
        uptime_seconds: Math.floor(process.uptime()),
        campaigns: { running, review, completed, paused },
        // Queue depths would be populated by a broker health check in production
        queues: {
          note: 'Queue depth monitoring requires broker connection',
        },
        timestamp: new Date().toISOString(),
      });
    } catch (err) {
      res.status(500).json({ status: 'error', error: (err as Error).message });
    }
  });

  return router;
}
