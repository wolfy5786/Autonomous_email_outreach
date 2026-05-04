import { Router, Request, Response } from 'express';

export function createHealthRouter(): Router {
  const router = Router();

  router.get('/health', (_req: Request, res: Response) => {
    res.json({
      status: 'ok',
      service: 'orchestrator',
      timestamp: new Date().toISOString(),
      uptime: process.uptime(),
    });
  });

  return router;
}
