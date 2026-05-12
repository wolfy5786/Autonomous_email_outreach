/**
 * Typed endpoint functions. Pages import these — they're the single source of
 * truth for what the gateway needs to implement.
 */

import { api } from "./client";
import type {
  Campaign,
  CampaignCreateRequest,
  CampaignSummary,
  CompanyDetail,
  Draft,
  EarlyAccessRequest,
  TraceEvent,
} from "./types";

export const endpoints = {
  // Campaigns
  listCampaigns: () => api.get<Campaign[]>("/api/campaigns"),
  getCampaign: (id: string) => api.get<Campaign>(`/api/campaigns/${id}`),
  createCampaign: (body: CampaignCreateRequest) =>
    api.post<Campaign>("/api/campaigns", body),

  // Companies
  listCampaignCompanies: (campaignId: string) =>
    api.get<CompanyDetail[]>(`/api/campaigns/${campaignId}/companies`),
  getCompany: (id: string) => api.get<CompanyDetail>(`/api/companies/${id}`),

  // Drafts
  listCampaignDrafts: (campaignId: string) =>
    api.get<Draft[]>(`/api/campaigns/${campaignId}/drafts`),
  getDraft: (id: string) => api.get<Draft>(`/api/drafts/${id}`),
  updateDraft: (id: string, body: Partial<Draft>) =>
    api.patch<Draft>(`/api/drafts/${id}`, body),

  // Observability (timeline embedded in campaign detail page)
  getCampaignTimeline: (campaignId: string) =>
    api.get<TraceEvent[]>(`/api/campaigns/${campaignId}/timeline`),
  getCampaignSummaries: () =>
    api.get<CampaignSummary[]>("/api/campaigns/summaries"),

  // Landing
  requestEarlyAccess: (body: EarlyAccessRequest) =>
    api.post<{ ok: true }>("/api/early-access", body),
};
