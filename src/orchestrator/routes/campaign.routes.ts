import { Router, Request, Response, NextFunction } from 'express';
import { PipelineService } from '../services';
import { CampaignStatusRepository } from '../postgres';

export function createCampaignRouter(
  pipelineService: PipelineService,
  statusRepo: CampaignStatusRepository
): Router {
  const router = Router();

  // POST /api/campaigns — create a new campaign
  router.post('/', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { name, icp } = req.body;
      const result = await pipelineService.createCampaign(name, icp);
      res.status(201).json(result);
    } catch (err) {
      next(err);
    }
  });

  // GET /api/campaigns — list all campaigns
  router.get('/', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const limit = parseInt(req.query.limit as string) || 50;
      const offset = parseInt(req.query.offset as string) || 0;
      const campaigns = await statusRepo.findAll(limit, offset);
      res.json({ campaigns, limit, offset });
    } catch (err) {
      next(err);
    }
  });

  // GET /api/campaigns/:id — campaign detail
  router.get('/:id', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const campaign = await statusRepo.findById(req.params.id);
      if (!campaign) {
        return res.status(404).json({ error: 'Campaign not found' });
      }
      res.json(campaign);
    } catch (err) {
      next(err);
    }
  });

  // PATCH /api/campaigns/:id — pause or resume
  router.patch('/:id', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { action } = req.body;
      if (action === 'pause') {
        await pipelineService.pauseCampaign(req.params.id);
      } else if (action === 'resume') {
        await pipelineService.resumeCampaign(req.params.id);
      } else {
        return res.status(400).json({ error: 'Action must be "pause" or "resume"' });
      }
      res.json({ status: 'ok', action });
    } catch (err) {
      next(err);
    }
  });

  // DELETE /api/campaigns/:id — cancel campaign
  router.delete('/:id', async (req: Request, res: Response, next: NextFunction) => {
    try {
      await pipelineService.cancelCampaign(req.params.id);
      res.json({ status: 'cancelled', campaignId: req.params.id });
    } catch (err) {
      next(err);
    }
  });

  return router;
}
