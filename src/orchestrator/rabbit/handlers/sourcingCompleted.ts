import { EventsBroker } from '../events-broker';
import { CampaignStatusRepository } from '../../postgres';
import { publishProspectingRequested } from '../publishers';
import { SourcingCompleted } from '../../types/events';

export function createSourcingCompletedHandler(
  broker: EventsBroker,
  statusRepo: CampaignStatusRepository
) {
  return async (msg: { payload: SourcingCompleted }): Promise<void> => {
    const { campaignId, companiesFound } = msg.payload;
    console.log(`[sourcingCompleted] Campaign ${campaignId} — ${companiesFound} companies found`);

    await statusRepo.updateStatus(campaignId, 'PROSPECTING');
    await publishProspectingRequested(broker, campaignId, companiesFound);

    console.log(`[sourcingCompleted] Triggered prospecting for campaign ${campaignId}`);
  };
}
