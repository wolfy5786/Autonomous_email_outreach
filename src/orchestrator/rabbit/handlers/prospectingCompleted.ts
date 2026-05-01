import { EventsBroker } from '../events-broker';
import { CampaignStatusRepository } from '../../postgres';
import { publishMessagingRequested } from '../publishers';
import { ProspectingCompleted } from '../../types/events';

export function createProspectingCompletedHandler(
  broker: EventsBroker,
  statusRepo: CampaignStatusRepository
) {
  return async (msg: { payload: ProspectingCompleted }): Promise<void> => {
    const { campaignId, prospectsEnriched } = msg.payload;
    console.log(`[prospectingCompleted] Campaign ${campaignId} — ${prospectsEnriched} prospects enriched`);

    await statusRepo.updateStatus(campaignId, 'MESSAGING');
    await publishMessagingRequested(broker, campaignId, prospectsEnriched);

    console.log(`[prospectingCompleted] Triggered messaging for campaign ${campaignId}`);
  };
}
