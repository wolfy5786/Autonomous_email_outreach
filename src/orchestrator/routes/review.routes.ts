import { Router, Request, Response, NextFunction } from 'express';
import { ReviewService } from '../services/review.service';
import { AppError } from '../middleware/error-handler';

export function createReviewRouter(reviewService: ReviewService): Router {
  const router = Router();

  // ── Draft Endpoints ────────────────────────────────────────

  // GET /drafts/:id — Get a specific draft
  router.get('/drafts/:id', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const draft = await reviewService.getDraft(String(req.params.id));
      if (!draft) throw new AppError(404, 'Draft not found');
      res.json(draft);
    } catch (err) {
      next(err);
    }
  });

  // PATCH /drafts/:id — Update draft subject or body
  router.patch('/drafts/:id', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { subject, body } = req.body;
      if (!subject && !body) {
        throw new AppError(400, 'Provide subject or body to update');
      }

      const draft = await reviewService.updateDraft(String(req.params.id), { subject, body });
      if (!draft) throw new AppError(404, 'Draft not found');
      res.json(draft);
    } catch (err) {
      next(err);
    }
  });

  // POST /drafts/:id/approve — Approve a draft → publishes send.requested
  router.post('/drafts/:id/approve', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const draft = await reviewService.approveDraft(String(req.params.id));
      if (!draft) throw new AppError(404, 'Draft not found or not in pending_review status');
      res.json({ message: 'Draft approved', draft });
    } catch (err) {
      next(err);
    }
  });

  // POST /drafts/:id/reject — Reject a draft with optional regeneration
  router.post('/drafts/:id/reject', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { notes, regenerate } = req.body;
      const draft = await reviewService.rejectDraft(String(req.params.id), notes, regenerate);
      if (!draft) throw new AppError(404, 'Draft not found or not in pending_review status');
      res.json({ message: 'Draft rejected', regeneration_requested: !!regenerate, draft });
    } catch (err) {
      next(err);
    }
  });

  // POST /drafts/:id/regenerate — Request a new draft for this prospect
  router.post(
    '/drafts/:id/regenerate',
    async (req: Request, res: Response, next: NextFunction) => {
      try {
        const { prompt } = req.body;
        const draft = await reviewService.regenerateDraft(String(req.params.id), prompt);
        if (!draft) throw new AppError(404, 'Draft not found');
        res.json({ message: 'Regeneration requested', draft });
      } catch (err) {
        next(err);
      }
    }
  );

  // ── Review UI Endpoints ──────────────────────────────────────

  // GET /review/queue — Get all drafts pending review
  router.get('/review/queue', async (_req: Request, res: Response, next: NextFunction) => {
    try {
      const drafts = await reviewService.getReviewQueue();
      res.json({ count: drafts.length, drafts });
    } catch (err) {
      next(err);
    }
  });

  // POST /review/bulk-approve — Approve a batch of draft IDs
  router.post('/review/bulk-approve', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const { draft_ids } = req.body;
      if (!Array.isArray(draft_ids) || draft_ids.length === 0) {
        throw new AppError(400, 'Provide an array of draft_ids');
      }

      const result = await reviewService.bulkApprove(draft_ids);
      res.json(result);
    } catch (err) {
      next(err);
    }
  });

  return router;
}
