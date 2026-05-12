import { Router, Request, Response, NextFunction } from 'express';
import { PipelineService } from '../services/pipeline.service';
import { Campaign } from '../../shared/models';
import { AppError } from '../middleware/error-handler';
import { CreateCampaignPayload } from '../../shared/types';

export function createCampaignRouter(pipelineService: PipelineService): Router {
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

  // GET /api/campaigns — List all campaigns with status
  router.get('/', async (_req: Request, res: Response, next: NextFunction) => {
    try {
      const campaigns = await Campaign.find()
        .sort({ created_at: -1 })
        .select('-__v');
      res.json(campaigns);
    } catch (err) {
      next(err);
    }
  });

  // GET /api/campaigns/:id — Get campaign details and pipeline status
  router.get('/:id', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const campaign = await Campaign.findOne({ campaign_id: String(req.params.id) }).select('-__v');
      if (!campaign) throw new AppError(404, 'Campaign not found');
      res.json(campaign);
    } catch (err) {
      next(err);
    }
  });

  // PATCH /api/campaigns/:id — Pause ({ status: "paused" }), resume ({ resume: true }), or patch config
  router.patch('/:id', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { status, resume, config: configUpdate } = req.body;
      const updates: Record<string, unknown> = {};

      const existing = await Campaign.findOne({ campaign_id: String(req.params.id) });
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
        { campaign_id: String(req.params.id) },
        { $set: updates },
        { new: true }
      );

      if (!campaign) throw new AppError(404, 'Campaign not found');
      res.json(campaign);
    } catch (err) {
      next(err);
    }
  });

  // DELETE /api/campaigns/:id — Cancel and archive a campaign
  router.delete('/:id', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const campaign = await Campaign.findOneAndUpdate(
        { campaign_id: String(req.params.id) },
        { $set: { status: 'cancelled' } },
        { new: true }
      );

      if (!campaign) throw new AppError(404, 'Campaign not found');
      res.json({ message: 'Campaign cancelled', campaign_id: String(req.params.id), status: 'cancelled' });
    } catch (err) {
      next(err);
    }
  });

  // GET /api/campaigns/:id/stats — Draft counts and success rate (no send/approval workflow)
  router.get('/:id/stats', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const campaign = await Campaign.findOne({ campaign_id: String(req.params.id) });
      if (!campaign) throw new AppError(404, 'Campaign not found');

      const ps = campaign.pipeline_state;
      const totalProspects = ps.ranked_prospect_ids.length;
      const draftsWritten = ps.draft_ids.length;
      const draftsFailed = ps.failed_draft_ids.length;

      res.json({
        campaign_id: campaign.campaign_id,
        status: campaign.status,
        current_stage: ps.current_stage,
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
      const campaign = await Campaign.findOne({ campaign_id: String(req.params.id) });
      if (!campaign) throw new AppError(404, 'Campaign not found');

      // Return the ranked prospect IDs from pipeline state.
      // Full prospect records would be fetched from the persons/companies collections.
      res.json({
        campaign_id: campaign.campaign_id,
        prospect_ids: campaign.pipeline_state.ranked_prospect_ids,
        count: campaign.pipeline_state.ranked_prospect_ids.length,
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
