import { Router, Request, Response, NextFunction } from 'express';
import { PipelineService } from '../services/pipeline.service';
import { Campaign } from '../../shared/models';
import { AppError } from '../middleware/error-handler';
import { CreateCampaignPayload } from '../../shared/types';

export function createCampaignRouter(pipelineService: PipelineService): Router {
  const router = Router();

  // POST /campaigns — Create and trigger a new outreach campaign
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

  // GET /campaigns — List all campaigns with status
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

  // GET /campaigns/:id — Get campaign details and pipeline status
  router.get('/:id', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const campaign = await Campaign.findOne({ campaign_id: String(req.params.id) }).select('-__v');
      if (!campaign) throw new AppError(404, 'Campaign not found');
      res.json(campaign);
    } catch (err) {
      next(err);
    }
  });

  // PATCH /campaigns/:id — Update campaign config (pause, resume, update send window)
  router.patch('/:id', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { status, config: configUpdate } = req.body;
      const updates: Record<string, unknown> = {};

      if (status) {
        if (!['paused', 'running'].includes(status)) {
          throw new AppError(400, 'Only paused/running transitions are allowed via PATCH');
        }
        updates.status = status;
      }

      if (configUpdate) {
        // Allow updating send_window and min_icp_score on a running campaign
        if (configUpdate.send_window) updates['config.send_window'] = configUpdate.send_window;
        if (configUpdate.min_icp_score != null)
          updates['config.min_icp_score'] = configUpdate.min_icp_score;
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

  // DELETE /campaigns/:id — Cancel and archive a campaign
  router.delete('/:id', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const campaign = await Campaign.findOneAndUpdate(
        { campaign_id: String(req.params.id) },
        { $set: { status: 'paused' } },
        { new: true }
      );

      if (!campaign) throw new AppError(404, 'Campaign not found');
      res.json({ message: 'Campaign cancelled', campaign_id: String(req.params.id) });
    } catch (err) {
      next(err);
    }
  });

  // GET /campaigns/:id/stats — Sent count, approval rate, bounce rate
  router.get('/:id/stats', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const campaign = await Campaign.findOne({ campaign_id: String(req.params.id) });
      if (!campaign) throw new AppError(404, 'Campaign not found');

      const ps = campaign.pipeline_state;
      const totalProspects = ps.ranked_prospect_ids.length;
      const draftsGenerated = ps.draft_ids.length;
      const emailsSent = ps.sent_draft_ids.length;
      const emailsFailed = ps.failed_draft_ids.length;
      const draftsApproved = emailsSent + emailsFailed;

      res.json({
        campaign_id: campaign.campaign_id,
        status: campaign.status,
        current_stage: ps.current_stage,
        stats: {
          total_prospects: totalProspects,
          drafts_generated: draftsGenerated,
          drafts_approved: draftsApproved,
          drafts_rejected: Math.max(0, draftsGenerated - draftsApproved),
          emails_sent: emailsSent,
          emails_failed: emailsFailed,
          approval_rate: draftsGenerated > 0 ? draftsApproved / draftsGenerated : 0,
          bounce_rate: emailsSent > 0 ? emailsFailed / (emailsSent + emailsFailed) : 0,
        },
        stage_timestamps: ps.stage_timestamps,
      });
    } catch (err) {
      next(err);
    }
  });

  // GET /campaigns/:id/prospects — List scored prospects (delegates to NoSQL query)
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

  // GET /campaigns/:id/drafts — List all drafts for a campaign
  router.get('/:id/drafts', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { EmailDraft } = await import('../models/email-draft.model');
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
