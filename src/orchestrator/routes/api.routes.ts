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
      const running = await Campaign.countDocuments({ status: 'running' });
      const inMessaging = await Campaign.countDocuments({
        status: 'running',
        'pipeline_state.current_stage': 'messaging',
      });
      const completed = await Campaign.countDocuments({ status: 'completed' });
      const paused = await Campaign.countDocuments({ status: 'paused' });

      res.json({
        service: 'orchestrator',
        uptime_seconds: Math.floor(process.uptime()),
        campaigns: { running, messaging: inMessaging, completed, paused },
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
