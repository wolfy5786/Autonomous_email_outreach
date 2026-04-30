import { EventsBroker } from '../events-broker';
import { CampaignStatusRepository } from '../../postgres';
import { publishSourcingRequested } from '../publishers';
import { PlanReady } from '../../types/events';

export function createPlanReadyHandler(
  broker: EventsBroker,
  statusRepo: CampaignStatusRepository
) {
  return async (msg: { payload: PlanReady }): Promise<void> => {
    const { campaignId, planId, sources } = msg.payload;
    console.log(`[planReady] Campaign ${campaignId} — plan ${planId} ready with ${sources.length} sources`);

    await statusRepo.updateStatus(campaignId, 'SOURCING');
    await publishSourcingRequested(broker, campaignId, planId, sources);

    console.log(`[planReady] Triggered sourcing for campaign ${campaignId}`);
  };
}
