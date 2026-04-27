export type CampaignStatus =
  | 'CREATED'
  | 'PLANNING'
  | 'PLAN_READY'
  | 'SOURCING'
  | 'SOURCING_FAILED'
  | 'PROSPECTING'
  | 'MESSAGING'
  | 'COMPLETED'
  | 'PAUSED'
  | 'CANCELLED';

export interface Campaign {
  id: string;
  name: string;
  icp: ICPDefinition;
  status: CampaignStatus;
  createdAt: Date;
  updatedAt: Date;
}

export interface ICPDefinition {
  industry: string;
  companySize: string;
  region: string;
  titles: string[];
  keywords: string[];
}

export interface CampaignStats {
  campaignId: string;
  totalProspects: number;
  emailsSent: number;
  opened: number;
  replied: number;
  openRate: number;
  replyRate: number;
}
