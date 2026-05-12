import { Router, Request, Response, NextFunction } from 'express';
import { Campaign, EmailDraft } from '../../shared/models';
import { AppError } from '../middleware/error-handler';

/**
 * Top-level `/api/*` routes from design_docs/orchestrator_service_role.md (sections 3.2–3.4)
 * (campaign routes live under `/api/campaigns` via campaign.routes.ts).
 */
export function createApiRouter(): Router {
  const router = Router();

  // GET /api/status — Queue depths, service statuses, DLQ count
  router.get('/status', async (_req: Request, res: Response, next: NextFunction) => {
    try {
      const PIPELINE_ACTIVE = ['planning', 'sourcing', 'prospecting', 'messaging'] as const;
      const active_pipeline = await Campaign.countDocuments({ status: { $in: PIPELINE_ACTIVE } });
      const in_messaging = await Campaign.countDocuments({ status: 'messaging' });
      const completed = await Campaign.countDocuments({ status: 'completed' });
      const paused = await Campaign.countDocuments({ status: 'paused' });
      const cancelled = await Campaign.countDocuments({ status: 'cancelled' });
      const failed = await Campaign.countDocuments({ status: 'failed' });

      res.json({
        service: 'orchestrator',
        uptime_seconds: Math.floor(process.uptime()),
        campaigns: {
          active_pipeline,
          in_messaging,
          completed,
          paused,
          cancelled,
          failed,
        },
        queues: {
          note: 'Queue depth / DLQ metrics require broker integration (stub)',
          depths: null,
          dlq_total: null,
        },
        timestamp: new Date().toISOString(),
      });
    } catch (err) {
      next(err);
    }
  });

  // GET /api/prospects/:id — Full prospect record (stub until enrichment store is wired)
  router.get('/prospects/:id', (req: Request, res: Response) => {
    res.status(200).json({
      stub: true,
      prospect_id: String(req.params.id),
      company: null,
      poc: null,
      icp_score: null,
      note: 'Prospect detail aggregation not implemented',
    });
  });

  // GET /api/drafts/:id — One draft record
  router.get('/drafts/:id', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const draft = await EmailDraft.findOne({ draft_id: String(req.params.id) }).select('-__v');
      if (!draft) throw new AppError(404, 'Draft not found');
      res.json(draft);
    } catch (err) {
      next(err);
    }
  });

  return router;
}
