// ── Campaign Types ───────────────────────────────────────────────

export type EmailChannel = 'smtp' | 'sendgrid' | 'postmark' | 'ses';

export type CampaignStatus = 'draft' | 'running' | 'review' | 'completed' | 'paused';

export type DraftStatus =
  | 'pending_review'
  | 'approved'
  | 'edited_approved'
  | 'rejected'
  | 'sent'
  | 'failed';

export type FundingStage =
  | 'bootstrapped'
  | 'seed'
  | 'series_a'
  | 'series_b'
  | 'growth'
  | 'public'
  | 'unknown';

export type Seniority =
  | 'ic'
  | 'manager'
  | 'director'
  | 'vp'
  | 'c_level'
  | 'founder'
  | 'unknown';

export interface SendWindow {
  start_hour: number;
  end_hour: number;
  timezone: string;
}

export interface CampaignConfig {
  email_channel: EmailChannel;
  email_channel_config: Record<string, unknown>;
  min_icp_score: number;
  freshness_days: number;
  send_window: SendWindow;
}

export interface ICPDefinition {
  industries?: string[];
  employee_count_range?: { min: number; max: number };
  funding_stages?: FundingStage[];
  geographies?: string[];
  tech_stack?: string[];
  target_titles?: string[];
  target_seniorities?: Seniority[];
  target_departments?: string[];
  [key: string]: unknown;
}

export interface ProductProfile {
  name: string;
  description: string;
  value_propositions?: string[];
  use_cases?: string[];
  differentiators?: string[];
  [key: string]: unknown;
}

export interface CreateCampaignPayload {
  name: string;
  icp: ICPDefinition;
  product_profile: ProductProfile;
  config: CampaignConfig;
}

// ── Queue Event Payloads ─────────────────────────────────────────

export interface PlanRequestedPayload {
  campaign_id: string;
}

export interface PlanReadyPayload {
  campaign_id: string;
  plan_id: string;
}

export interface SourcingRequestedPayload {
  campaign_id: string;
  plan_id: string;
  target_entities: string[];
}

export interface SourcingCompletedPayload {
  campaign_id: string;
  entity_ids: string[];
}

export interface SourcingPartialPayload {
  campaign_id: string;
  entity_id: string;
  missing_fields: string[];
}

export interface ProspectingCompletedPayload {
  campaign_id: string;
  ranked_prospects: Array<{ poc_id: string; score: number }>;
}

export interface MessagingRequestedPayload {
  campaign_id: string;
  poc_id: string;
  regeneration_prompt?: string;
}

export interface MessagingCompletedPayload {
  campaign_id: string;
  draft_id: string;
}

export interface ReviewCompletedPayload {
  draft_id: string;
  decision: 'approve' | 'reject';
  notes?: string;
}

export interface SendRequestedPayload {
  draft_id: string;
}

export interface SendCompletedPayload {
  draft_id: string;
  message_id: string;
  sent_at: string;
}

export interface SendFailedPayload {
  draft_id: string;
  error: string;
  retry_count: number;
}

export interface CampaignCompletedPayload {
  campaign_id: string;
  stats: CampaignStats;
}

export interface CampaignStats {
  total_prospects: number;
  drafts_generated: number;
  drafts_approved: number;
  drafts_rejected: number;
  emails_sent: number;
  emails_failed: number;
  approval_rate: number;
  bounce_rate: number;
}

// ── Pipeline Stage Tracking ──────────────────────────────────────

export type PipelineStage =
  | 'planning'
  | 'sourcing'
  | 'prospecting'
  | 'messaging'
  | 'review'
  | 'sending'
  | 'completed';

export interface PipelineState {
  current_stage: PipelineStage;
  plan_id?: string;
  sourced_entity_ids: string[];
  ranked_prospect_ids: string[];
  draft_ids: string[];
  sent_draft_ids: string[];
  failed_draft_ids: string[];
  stage_timestamps: Partial<Record<PipelineStage, string>>;
}
