/**
 * Typed endpoint functions. Pages import these — they're the single source of
 * truth for what the gateway needs to implement.
 */

import { api } from "./client";
import {
  normalizeCampaignDetailResponse,
  normalizeCampaignFromMongoDoc,
  normalizeCampaignListRow,
  type OrchestratorCampaignCreatePayload,
} from "./normalize";
import type {
  Campaign,
  CampaignSummary,
  CompanyDetail,
  Draft,
  EarlyAccessRequest,
  TraceEvent,
} from "./types";

function isPlainObject(x: unknown): x is Record<string, unknown> {
  return typeof x === "object" && x !== null && !Array.isArray(x);
}

export const endpoints = {
  // Campaigns
  listCampaigns: async () => {
    const rows = await api.get<unknown[]>("/api/campaigns");
    if (!Array.isArray(rows)) return [];
    return rows.map((row) => {
      if (isPlainObject(row) && "campaign_id" in row) {
        return normalizeCampaignListRow(row);
      }
      return row as Campaign;
    });
  },

  getCampaign: async (id: string) => {
    const raw = await api.get<unknown>(`/api/campaigns/${id}`);
    if (isPlainObject(raw) && ("campaign" in raw || "campaign_id" in raw)) {
      return normalizeCampaignDetailResponse(raw);
    }
    return raw as Campaign;
  },

  createCampaign: async (body: OrchestratorCampaignCreatePayload) => {
    const raw = await api.post<unknown>("/api/campaigns", body);
    if (isPlainObject(raw)) {
      return normalizeCampaignFromMongoDoc(raw);
    }
    return raw as Campaign;
  },

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
