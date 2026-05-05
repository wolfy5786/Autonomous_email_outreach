import mongoose from 'mongoose';
import { CampaignStats } from '../types/campaign';

export class StatsAggregator {
  async getCampaignStats(campaignId: string): Promise<CampaignStats> {
    const db = mongoose.connection.db;

    const totalProspects = await db
      .collection('prospects')
      .countDocuments({ campaignId });

    const drafts = await db
      .collection('drafts')
      .find({ campaignId })
      .toArray();

    const emailsSent = drafts.filter((d) => d.status === 'SENT').length;
    const opened = drafts.filter((d) => d.opened === true).length;
    const replied = drafts.filter((d) => d.replied === true).length;

    return {
      campaignId,
      totalProspects,
      emailsSent,
      opened,
      replied,
      openRate: emailsSent > 0 ? (opened / emailsSent) * 100 : 0,
      replyRate: emailsSent > 0 ? (replied / emailsSent) * 100 : 0,
    };
  }
}
