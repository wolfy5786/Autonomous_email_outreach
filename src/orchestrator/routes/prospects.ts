import { Router, Request, Response, NextFunction } from 'express';
import mongoose from 'mongoose';

export function createProspectsRouter(): Router {
  const router = Router();

  // GET /api/campaigns/:id/prospects
  router.get('/campaigns/:id/prospects', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const campaignId = req.params.id;
      const db = mongoose.connection.db;
      const prospects = await db
        .collection('prospects')
        .find({ campaignId })
        .limit(100)
        .toArray();

      res.json({ campaignId, count: prospects.length, prospects });
    } catch (err) {
      next(err);
    }
  });

  // GET /api/prospects/:id
  router.get('/prospects/:id', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const db = mongoose.connection.db;
      const prospect = await db
        .collection('prospects')
        .findOne({ _id: new mongoose.Types.ObjectId(req.params.id) });

      if (!prospect) return res.status(404).json({ error: 'Prospect not found' });
      res.json(prospect);
    } catch (err) {
      next(err);
    }
  });

  return router;
}
