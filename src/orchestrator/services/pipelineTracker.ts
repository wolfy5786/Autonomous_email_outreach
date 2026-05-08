import { CampaignStatusRepository } from '../postgres';
import { CampaignStatus } from '../types/campaign';

interface StageTransition {
  from: CampaignStatus;
  to: CampaignStatus;
  timestamp: Date;
}

export class PipelineTracker {
  private transitions: Map<string, StageTransition[]> = new Map();

  constructor(private statusRepo: CampaignStatusRepository) {}

  async recordTransition(campaignId: string, from: CampaignStatus, to: CampaignStatus): Promise<void> {
    const transition: StageTransition = { from, to, timestamp: new Date() };

    if (!this.transitions.has(campaignId)) {
      this.transitions.set(campaignId, []);
    }
    this.transitions.get(campaignId)!.push(transition);

    await this.statusRepo.updateStatus(campaignId, to);
    console.log(`[PipelineTracker] Campaign ${campaignId}: ${from} → ${to}`);
  }

  getTransitions(campaignId: string): StageTransition[] {
    return this.transitions.get(campaignId) || [];
  }

  async getCurrentStage(campaignId: string): Promise<CampaignStatus | null> {
    const row = await this.statusRepo.findById(campaignId);
    return row?.status ?? null;
  }
}
