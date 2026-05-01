import { EventsBroker } from '../events-broker';
import { MessagingFailed } from '../../types/events';

const MAX_RETRIES = 3;

export function createMessagingFailedHandler(broker: EventsBroker) {
  return async (msg: { payload: MessagingFailed }): Promise<void> => {
    const { campaignId, draftId, error, retryCount } = msg.payload;
    console.warn(`[messagingFailed] Draft ${draftId} for campaign ${campaignId}: ${error}`);

    if (retryCount < MAX_RETRIES) {
      console.log(`[messagingFailed] Re-queuing draft ${draftId} (retry ${retryCount + 1})`);
      await broker.publish('messaging.retry', {
        campaignId,
        draftId,
        retryCount: retryCount + 1,
        timestamp: new Date().toISOString(),
      });
    } else {
      console.error(`[messagingFailed] Draft ${draftId} permanently failed after ${MAX_RETRIES} retries`);
    }
  };
}
