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

  // GET /api/drafts/:id — One draft record, joined with recipient (POC + company)
  // so the UI can render a Gmail-style "From / To / Subject" header without
  // separate roundtrips to persons/companies.
  router.get('/drafts/:id', async (req: Request, res: Response, next: NextFunction) => {
    try {
      // Python messaging writes drafts with id = uuid (and _id = same uuid).
      // Mongoose can't query _id with a UUID (would try to cast to ObjectId),
      // so use the `id` field; fall back to `draft_id` for any future writers.
      const draftId = String(req.params.id);
      const draft = await EmailDraft.findOne({
        $or: [{ id: draftId }, { draft_id: draftId }],
      })
        .select('-__v')
        .lean();
      if (!draft) throw new AppError(404, 'Draft not found');

      // Raw collection access — persons + companies are owned by other services
      // (Beanie/Python) and not modeled in Mongoose here.
      const db = EmailDraft.db.db;
      const [poc, company] = db
        ? await Promise.all([
            db.collection('persons').findOne({ _id: draft.poc_id as unknown as never }),
            db.collection('companies').findOne({ _id: draft.company_id as unknown as never }),
          ])
        : [null, null];

      const pocName =
        (poc?.name as string | undefined) ??
        ([poc?.first_name, poc?.last_name].filter(Boolean).join(' ').trim() || null);

      res.json({
        ...draft,
        recipient: {
          name: pocName,
          email: (poc?.email as string | null) ?? null,
          company: (company?.name as string | null) ?? null,
          company_domain: (company?.domain as string | null) ?? null,
          linkedin_url: (poc?.linkedin_url as string | null) ?? null,
        },
      });
    } catch (err) {
      next(err);
    }
  });

  return router;
}
