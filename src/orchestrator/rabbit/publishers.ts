import { EventsBroker } from './events-broker';
import { ICPDefinition } from '../types/campaign';

export async function publishPlanRequested(
  broker: EventsBroker,
  campaignId: string,
  icp: ICPDefinition
): Promise<void> {
  await broker.publish('plan.requested', {
    campaignId,
    icp,
    timestamp: new Date().toISOString(),
  });
}

export async function publishSourcingRequested(
  broker: EventsBroker,
  campaignId: string,
  planId: string,
  sources: string[]
): Promise<void> {
  await broker.publish('sourcing.requested', {
    campaignId,
    planId,
    sources,
    timestamp: new Date().toISOString(),
  });
}

export async function publishProspectingRequested(
  broker: EventsBroker,
  campaignId: string,
  companiesFound: number
): Promise<void> {
  await broker.publish('prospecting.requested', {
    campaignId,
    companiesFound,
    timestamp: new Date().toISOString(),
  });
}

export async function publishMessagingRequested(
  broker: EventsBroker,
  campaignId: string,
  prospectsEnriched: number
): Promise<void> {
  await broker.publish('messaging.requested', {
    campaignId,
    prospectsEnriched,
    timestamp: new Date().toISOString(),
  });
}
