import { Router, Request, Response, NextFunction } from 'express';
import mongoose from 'mongoose';

export function createDraftsRouter(): Router {
  const router = Router();

  // GET /api/campaigns/:id/drafts
  router.get('/campaigns/:id/drafts', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const campaignId = req.params.id;
      const db = mongoose.connection.db;
      const drafts = await db
        .collection('drafts')
        .find({ campaignId })
        .sort({ createdAt: -1 })
        .limit(100)
        .toArray();

      res.json({ campaignId, count: drafts.length, drafts });
    } catch (err) {
      next(err);
    }
  });

  // GET /api/drafts/:id
  router.get('/drafts/:id', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const db = mongoose.connection.db;
      const draft = await db
        .collection('drafts')
        .findOne({ _id: new mongoose.Types.ObjectId(req.params.id) });

      if (!draft) return res.status(404).json({ error: 'Draft not found' });
      res.json(draft);
    } catch (err) {
      next(err);
    }
  });

  return router;
}
