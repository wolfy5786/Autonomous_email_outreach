export interface PlanRequested {
  type: 'plan.requested';
  campaignId: string;
  icp: {
    industry: string;
    companySize: string;
    region: string;
    titles: string[];
    keywords: string[];
  };
  timestamp: string;
}

export interface PlanReady {
  type: 'plan.ready';
  campaignId: string;
  planId: string;
  sources: string[];
  timestamp: string;
}

export interface SourcingCompleted {
  type: 'sourcing.completed';
  campaignId: string;
  companiesFound: number;
  timestamp: string;
}

export interface SourcingFailed {
  type: 'sourcing.failed';
  campaignId: string;
  error: string;
  retryCount: number;
  timestamp: string;
}

export interface ProspectingCompleted {
  type: 'prospecting.completed';
  campaignId: string;
  prospectsEnriched: number;
  timestamp: string;
}

export interface MessagingFailed {
  type: 'messaging.failed';
  campaignId: string;
  draftId: string;
  error: string;
  retryCount: number;
  timestamp: string;
}

export type PipelineEvent =
  | PlanRequested
  | PlanReady
  | SourcingCompleted
  | SourcingFailed
  | ProspectingCompleted
  | MessagingFailed;
