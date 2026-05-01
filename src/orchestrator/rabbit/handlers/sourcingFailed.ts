import { EventsBroker } from '../events-broker';
import { CampaignStatusRepository } from '../../postgres';
import { SourcingFailed } from '../../types/events';

const MAX_RETRIES = 3;

export function createSourcingFailedHandler(
  broker: EventsBroker,
  statusRepo: CampaignStatusRepository
) {
  return async (msg: { payload: SourcingFailed }): Promise<void> => {
    const { campaignId, error, retryCount } = msg.payload;
    console.warn(`[sourcingFailed] Campaign ${campaignId} — attempt ${retryCount}: ${error}`);

    if (retryCount < MAX_RETRIES) {
      console.log(`[sourcingFailed] Retrying sourcing (${retryCount + 1}/${MAX_RETRIES})...`);
      await broker.publish('sourcing.requested', {
        campaignId,
        retryCount: retryCount + 1,
        timestamp: new Date().toISOString(),
      });
    } else {
      console.error(`[sourcingFailed] Max retries reached for campaign ${campaignId}`);
      await statusRepo.updateStatus(campaignId, 'SOURCING_FAILED');
    }
  };
}
