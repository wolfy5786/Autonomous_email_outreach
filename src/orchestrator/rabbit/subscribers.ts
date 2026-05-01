import { EventsBroker } from './events-broker';
import { CampaignStatusRepository } from '../postgres';
import { createPlanReadyHandler } from './handlers/planReady';
import { createSourcingCompletedHandler } from './handlers/sourcingCompleted';
import { createSourcingFailedHandler } from './handlers/sourcingFailed';
import { createProspectingCompletedHandler } from './handlers/prospectingCompleted';
import { createMessagingFailedHandler } from './handlers/messagingFailed';

export async function registerSubscribers(
  broker: EventsBroker,
  statusRepo: CampaignStatusRepository
): Promise<void> {
  await broker.subscribe(
    'plan.ready',
    'orchestrator.plan-ready',
    createPlanReadyHandler(broker, statusRepo)
  );

  await broker.subscribe(
    'sourcing.completed',
    'orchestrator.sourcing-completed',
    createSourcingCompletedHandler(broker, statusRepo)
  );

  await broker.subscribe(
    'sourcing.failed',
    'orchestrator.sourcing-failed',
    createSourcingFailedHandler(broker, statusRepo)
  );

  await broker.subscribe(
    'prospecting.completed',
    'orchestrator.prospecting-completed',
    createProspectingCompletedHandler(broker, statusRepo)
  );

  await broker.subscribe(
    'messaging.failed',
    'orchestrator.messaging-failed',
    createMessagingFailedHandler(broker)
  );

  console.log('[subscribers] All pipeline event listeners registered');
}
