import { Router, Request, Response, NextFunction } from 'express';
import { PipelineService } from '../services/pipeline.service';
import { Campaign } from '../../shared/models';
import { AppError } from '../middleware/error-handler';
import { CreateCampaignPayload } from '../../shared/types';
import { CampaignStatusRepository } from '../postgres';

export function createCampaignRouter(
  pipelineService: PipelineService,
  statusRepo: CampaignStatusRepository
): Router {
  const router = Router();

  // POST /api/campaigns — Create and trigger a new outreach campaign
  router.post('/', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const payload = req.body as CreateCampaignPayload;

      if (!payload.name || !payload.icp || !payload.product_profile || !payload.config) {
        throw new AppError(400, 'Missing required fields: name, icp, product_profile, config');
      }

      const campaign = await pipelineService.createCampaign(payload);
      res.status(201).json(campaign);
    } catch (err) {
      next(err);
    }
  });

  // GET /api/campaigns — List all campaigns. Status comes from Postgres (§2.1),
  // names/config from Mongo (§2.2); joined on campaign_id.
  router.get('/', async (_req: Request, res: Response, next: NextFunction) => {
    try {
      const statusRows = await statusRepo.list();
      const ids = statusRows.map((r) => r.campaign_id);
      const docs = await Campaign.find({ campaign_id: { $in: ids } })
        .select('campaign_id name created_at updated_at icp')
        .lean();
      const byId = new Map(docs.map((d) => [d.campaign_id, d]));

      const out = statusRows.map((s) => {
        const doc = byId.get(s.campaign_id);
        return {
          campaign_id: s.campaign_id,
          name: doc?.name ?? null,
          status: s.status,
          current_stage: s.current_stage,
          plan_id: s.plan_id,
          last_error: s.last_error,
          created_at: doc?.created_at ?? s.created_at,
          updated_at: s.updated_at,
          icp: doc?.icp ?? null,
        };
      });
      res.json(out);
    } catch (err) {
      next(err);
    }
  });

  // GET /api/campaigns/:id — Combine Postgres status (§2.1) with Mongo content (§2.2).
  router.get('/:id', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const id = String(req.params.id);
      const [statusRow, doc] = await Promise.all([
        statusRepo.find(id),
        Campaign.findOne({ campaign_id: id }).select('-__v'),
      ]);
      if (!doc && !statusRow) throw new AppError(404, 'Campaign not found');

      res.json({
        campaign_id: id,
        status: statusRow?.status ?? doc?.status ?? null,
        current_stage:
          statusRow?.current_stage ?? doc?.pipeline_state?.current_stage ?? null,
        plan_id: statusRow?.plan_id ?? doc?.plan_id ?? null,
        last_error: statusRow?.last_error ?? null,
        updated_at: statusRow?.updated_at ?? doc?.updated_at ?? null,
        campaign: doc,
      });
    } catch (err) {
      next(err);
    }
  });

  // PATCH /api/campaigns/:id — Pause ({ status: "paused" }), resume ({ resume: true }), or patch config
  router.patch('/:id', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const id = String(req.params.id);
      const { status, resume, config: configUpdate } = req.body;
      const updates: Record<string, unknown> = {};

      const existing = await Campaign.findOne({ campaign_id: id });
      if (!existing) throw new AppError(404, 'Campaign not found');

      if (resume === true) {
        if (existing.status !== 'paused') {
          throw new AppError(400, 'resume is only valid when campaign status is paused');
        }
        const stage = existing.pipeline_state.current_stage;
        if (!['planning', 'sourcing', 'prospecting', 'messaging'].includes(stage)) {
          throw new AppError(400, 'Cannot resume from terminal pipeline stage');
        }
        updates.status = stage;
      } else if (status !== undefined && status !== null) {
        if (status !== 'paused') {
          throw new AppError(
            400,
            'Only status "paused" is supported via PATCH (use { resume: true } to continue)'
          );
        }
        updates.status = 'paused';
      }

      if (configUpdate) {
        if (configUpdate.send_window) updates['config.send_window'] = configUpdate.send_window;
        if (configUpdate.min_icp_score != null)
          updates['config.min_icp_score'] = configUpdate.min_icp_score;
        if (configUpdate.max_drafts != null) updates['config.max_drafts'] = configUpdate.max_drafts;
        if (configUpdate.freshness_days != null)
          updates['config.freshness_days'] = configUpdate.freshness_days;
        if (configUpdate.email_account) updates['config.email_account'] = configUpdate.email_account;
      }

      if (Object.keys(updates).length === 0) {
        res.json(existing);
        return;
      }

      const campaign = await Campaign.findOneAndUpdate(
        { campaign_id: id },
        { $set: updates },
        { new: true }
      );

      if (!campaign) throw new AppError(404, 'Campaign not found');

      // Mirror status changes into Postgres.
      if (updates.status !== undefined) {
        await statusRepo.setStatus(id, updates.status as never);
      }

      res.json(campaign);
    } catch (err) {
      next(err);
    }
  });

  // DELETE /api/campaigns/:id — Cancel and archive a campaign
  router.delete('/:id', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const id = String(req.params.id);
      const campaign = await Campaign.findOneAndUpdate(
        { campaign_id: id },
        { $set: { status: 'cancelled' } },
        { new: true }
      );

      if (!campaign) throw new AppError(404, 'Campaign not found');
      await statusRepo.setStatus(id, 'cancelled');
      res.json({ message: 'Campaign cancelled', campaign_id: id, status: 'cancelled' });
    } catch (err) {
      next(err);
    }
  });

  // GET /api/campaigns/:id/stats — Draft counts and success rate (no send/approval workflow)
  router.get('/:id/stats', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const id = String(req.params.id);
      const campaign = await Campaign.findOne({ campaign_id: id });
      if (!campaign) throw new AppError(404, 'Campaign not found');

      const statusRow = await statusRepo.find(id);
      const ps = campaign.pipeline_state;
      const totalProspects = ps.ranked_prospect_ids.length;
      const draftsWritten = ps.draft_ids.length;
      const draftsFailed = ps.failed_draft_ids.length;

      res.json({
        campaign_id: campaign.campaign_id,
        status: statusRow?.status ?? campaign.status,
        current_stage: statusRow?.current_stage ?? ps.current_stage,
        stats: {
          total_prospects: totalProspects,
          drafts_written: draftsWritten,
          drafts_failed: draftsFailed,
          draft_success_rate: totalProspects > 0 ? draftsWritten / totalProspects : 0,
        },
        stage_timestamps: ps.stage_timestamps,
      });
    } catch (err) {
      next(err);
    }
  });

  // GET /api/campaigns/:id/prospects — List scored prospects (delegates to NoSQL query)
  router.get('/:id/prospects', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const id = String(req.params.id);
      const campaign = await Campaign.findOne({ campaign_id: id });
      if (!campaign) throw new AppError(404, 'Campaign not found');

      const ids = campaign.pipeline_state.ranked_prospect_ids;
      const scores = campaign.pipeline_state.ranked_prospect_scores ?? {};
      res.json({
        campaign_id: campaign.campaign_id,
        count: ids.length,
        prospects: ids.map((poc_id) => ({ poc_id, score: scores[poc_id] ?? null })),
      });
    } catch (err) {
      next(err);
    }
  });

  // GET /api/campaigns/:id/drafts — List all drafts for a campaign
  router.get('/:id/drafts', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { EmailDraft } = await import('../../shared/models');
      const status = req.query.status as string | undefined;
      const filter: Record<string, unknown> = { campaign_id: String(req.params.id) };
      if (status) filter.status = status;

      const drafts = await EmailDraft.find(filter).sort({ generated_at: -1 });
      res.json(drafts);
    } catch (err) {
      next(err);
    }
  });

  return router;
}
