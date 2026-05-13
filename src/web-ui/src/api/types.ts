/**
 * Wire-format types for the operator UI ↔ gateway contract.
 *
 * These mirror the Python Pydantic / Beanie models in src/shared/models/.
 * When the gateway service is built, it should return these shapes verbatim
 * (snake_case keys preserved for fidelity with the rest of the system).
 */

/**
 * UI statuses include legacy mock values and Orchestrator lifecycle values
 * (see src/shared/types/index.ts).
 */
export type CampaignStatus =
  | "pending"
  | "draft"
  | "planning"
  | "sourcing"
  | "prospecting"
  | "drafting"
  | "messaging"
  | "paused"
  | "ready_for_review"
  | "completed"
  | "failed"
  | "cancelled";

export interface ICP {
  industry: string;
  employee_range: [number, number];
  stack_includes: string[];
  geography: string[];
  pain: string;
  /** Optional operator notes passed through to planning / messaging context. */
  additional_comment?: string;
  /** One-sentence desired outcome — fed to the planning LLM. */
  campaign_goal?: string;
}

export interface ProductProfile {
  name: string;
  value_prop: string;
  pricing?: string;
  differentiators?: string[];
}

export interface Campaign {
  id: string;
  name: string;
  icp: ICP;
  product_profile: ProductProfile;
  status: CampaignStatus;
  plan_id?: string;
  created_at: string;
  /** Aggregate counts populated server-side for list/detail views. */
  counts?: {
    companies: number;
    pocs: number;
    drafts: number;
  };
}

export interface Headquarters {
  city?: string;
  region?: string;
  country?: string;
}

export interface Company {
  id: string;
  name: string;
  domain?: string;
  industry?: string;
  employee_count?: number;
  hq?: Headquarters;
  /** Last sourcing scrape mode applied to this record. */
  last_scrape_mode?: "all" | "partial" | "none";
  /** Source-system identifiers and free-form attributes. */
  extra?: Record<string, unknown>;
}

export interface PersonOfContact {
  id: string;
  company_id: string;
  full_name: string;
  title?: string;
  email?: string;
  linkedin_url?: string;
  seniority?: string;
}

export interface CompanyDetail extends Company {
  pocs: PersonOfContact[];
}

export type DraftStatus =
  | "generating"
  | "draft_created"
  | "failed";

export interface LLMUsage {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

export interface Draft {
  id: string;
  campaign_id: string;
  company_id: string;
  poc_id: string;
  subject: string;
  body: string;
  personalization_hooks: string[];
  generated_at: string;
  status: DraftStatus;
  email_draft_ref?: string;
  email_provider?: "gmail" | "microsoft" | "stub";
  error?: string;
  retry_count: number;
  llm_model?: string;
  llm_usage?: LLMUsage;
}

export type TracePhase = "start" | "end" | "error" | "emit";

export interface TraceEvent {
  id: string;
  trace_id: string;
  campaign_id: string | null;
  service: string;
  event_name: string;
  phase: TracePhase;
  timestamp: string;
  duration_ms: number | null;
  error_type: string | null;
  error_message: string | null;
  metadata: Record<string, unknown>;
}

export interface CampaignSummary {
  campaign_id: string;
  first_seen: string;
  last_seen: string;
  event_count: number;
  services: string[];
}

export interface EarlyAccessRequest {
  email: string;
}
