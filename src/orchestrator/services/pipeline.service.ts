import { v4 as uuidv4 } from 'uuid';
import { EventsBroker } from '../rabbit/events-broker';
import { registerSubscribers } from '../rabbit/subscribers';
import { publishPlanRequested } from '../rabbit/publishers';
import { CampaignStatusRepository } from '../postgres';
import { validateICP, validateCampaignName } from './validation';
import { ICPDefinition } from '../types/campaign';

export class PipelineService {
  constructor(
    private broker: EventsBroker,
    private statusRepo: CampaignStatusRepository
  ) {}

  async startListening(): Promise<void> {
    await this.broker.init();
    await registerSubscribers(this.broker, this.statusRepo);
    console.log('[PipelineService] Listening for pipeline events');
  }

  async createCampaign(name: string, icp: unknown): Promise<{ campaignId: string }> {
    validateCampaignName(name);
    validateICP(icp);

    const campaignId = uuidv4();
    await this.statusRepo.upsert(campaignId, 'CREATED', { name, icp });
    await this.statusRepo.updateStatus(campaignId, 'PLANNING');
    await publishPlanRequested(this.broker, campaignId, icp as ICPDefinition);

    console.log(`[PipelineService] Campaign ${campaignId} created and plan.requested published`);
    return { campaignId };
  }

  async pauseCampaign(campaignId: string): Promise<void> {
    const campaign = await this.statusRepo.findById(campaignId);
    if (!campaign) throw new Error(`Campaign ${campaignId} not found`);
    if (campaign.status === 'PAUSED') throw new Error('Campaign is already paused');
    await this.statusRepo.updateStatus(campaignId, 'PAUSED');
  }

  async resumeCampaign(campaignId: string): Promise<void> {
    const campaign = await this.statusRepo.findById(campaignId);
    if (!campaign) throw new Error(`Campaign ${campaignId} not found`);
    if (campaign.status !== 'PAUSED') throw new Error('Campaign is not paused');
    await this.statusRepo.updateStatus(campaignId, 'PLANNING');
  }

  async cancelCampaign(campaignId: string): Promise<void> {
    const campaign = await this.statusRepo.findById(campaignId);
    if (!campaign) throw new Error(`Campaign ${campaignId} not found`);
    await this.statusRepo.updateStatus(campaignId, 'CANCELLED');
  }
}
