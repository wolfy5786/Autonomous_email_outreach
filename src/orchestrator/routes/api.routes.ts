import { Router, Request, Response, NextFunction } from 'express';
import { Campaign, EmailDraft } from '../../shared/models';
import { AppError } from '../middleware/error-handler';
import { CampaignStatusRepository } from '../postgres';

/**
 * Top-level `/api/*` routes from design_docs/orchestrator_service_role.md (sections 3.2–3.4)
 * (campaign routes live under `/api/campaigns` via campaign.routes.ts).
 */
export function createApiRouter(statusRepo: CampaignStatusRepository): Router {
  const router = Router();

  // GET /api/status — Service status (Postgres-backed campaign counts per §2.1).
  router.get('/status', async (_req: Request, res: Response, next: NextFunction) => {
    try {
      const counts = await statusRepo.countByStatus();
      const PIPELINE_ACTIVE = ['planning', 'sourcing', 'prospecting', 'messaging'];
      const active_pipeline = PIPELINE_ACTIVE.reduce(
        (sum, s) => sum + (counts[s] ?? 0),
        0
      );

      res.json({
        service: 'orchestrator',
        uptime_seconds: Math.floor(process.uptime()),
        campaigns: {
          active_pipeline,
          in_messaging: counts['messaging'] ?? 0,
          completed: counts['completed'] ?? 0,
          paused: counts['paused'] ?? 0,
          cancelled: counts['cancelled'] ?? 0,
          failed: counts['failed'] ?? 0,
          by_status: counts,
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

  // GET /api/prospects/:id — Prospect detail joined across campaigns and drafts.
  router.get('/prospects/:id', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const poc_id = String(req.params.id);

      // A poc_id can appear in multiple campaigns; return all matches.
      const campaigns = await Campaign.find({
        'pipeline_state.ranked_prospect_ids': poc_id,
      })
        .select('campaign_id name pipeline_state.ranked_prospect_scores config.min_icp_score')
        .lean();

      if (campaigns.length === 0) {
        throw new AppError(404, 'Prospect not found in any campaign');
      }

      const drafts = await EmailDraft.find({ poc_id })
        .select('draft_id campaign_id status generated_at')
        .lean();

      res.json({
        poc_id,
        campaigns: campaigns.map((c) => ({
          campaign_id: c.campaign_id,
          name: c.name,
          score: c.pipeline_state?.ranked_prospect_scores?.[poc_id] ?? null,
          min_icp_score: c.config?.min_icp_score ?? null,
        })),
        drafts,
      });
    } catch (err) {
      next(err);
    }
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
