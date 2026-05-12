import { Router, Request, Response } from 'express';

export function createHealthRouter(): Router {
  const router = Router();

  // GET /health — Service liveness check (outside /api per common probe conventions)
  router.get('/health', (_req: Request, res: Response) => {
    res.json({ status: 'ok', service: 'orchestrator', timestamp: new Date().toISOString() });
  });

  return router;
}
