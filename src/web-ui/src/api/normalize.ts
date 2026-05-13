/**
 * Map Orchestrator / Mongo campaign documents to the UI `Campaign` model.
 */

import type { Campaign, CampaignStatus, ICP, ProductProfile } from "./types";

export type OrchestratorCampaignCreatePayload = {
  name: string;
  icp: Record<string, unknown>;
  product_profile: {
    name: string;
    description: string;
    differentiators?: string[];
    [key: string]: unknown;
  };
  config: {
    email_account: { provider: "gmail" | "microsoft"; credentials_ref: string };
    min_icp_score: number;
    freshness_days: number;
    max_drafts: number;
  };
};

function isPlainObject(x: unknown): x is Record<string, unknown> {
  return typeof x === "object" && x !== null && !Array.isArray(x);
}

export function mapOrchestratorStatus(raw: string): CampaignStatus {
  if (
    raw === "pending" ||
    raw === "planning" ||
    raw === "sourcing" ||
    raw === "prospecting" ||
    raw === "messaging" ||
    raw === "paused" ||
    raw === "completed" ||
    raw === "failed" ||
    raw === "cancelled"
  ) {
    return raw;
  }
  if (raw === "draft" || raw === "drafting" || raw === "ready_for_review") {
    return raw;
  }
  return "planning";
}

export function parseIcp(raw: unknown): ICP {
  if (!isPlainObject(raw)) {
    return {
      industry: "",
      employee_range: [0, 0],
      stack_includes: [],
      geography: [],
      pain: "",
    };
  }
  const r = raw;
  const industries = r.industries as string[] | undefined;
  const industrySingle = r.industry as string | undefined;
  const industry =
    typeof industrySingle === "string" && industrySingle.length > 0
      ? industrySingle
      : (industries?.[0] ?? "");

  const ec = r.employee_count_range as { min?: number; max?: number } | undefined;
  const tuple = r.employee_range as unknown;
  let employee_range: [number, number];
  if (ec && typeof ec.min === "number" && typeof ec.max === "number") {
    employee_range = [ec.min, ec.max];
  } else if (
    Array.isArray(tuple) &&
    tuple.length >= 2 &&
    typeof tuple[0] === "number" &&
    typeof tuple[1] === "number"
  ) {
    employee_range = [tuple[0], tuple[1]];
  } else {
    employee_range = [0, 0];
  }

  const stackRaw = r.stack_includes ?? r.tech_stack;
  const stack_includes = Array.isArray(stackRaw)
    ? stackRaw.map((s) => String(s))
    : [];

  const geoRaw = r.geography ?? r.geographies;
  const geography = Array.isArray(geoRaw) ? geoRaw.map((s) => String(s)) : [];

  return {
    industry,
    employee_range,
    stack_includes,
    geography,
    pain: typeof r.pain === "string" ? r.pain : "",
    additional_comment:
      typeof r.additional_comment === "string"
        ? r.additional_comment
        : undefined,
    campaign_goal:
      typeof r.campaign_goal === "string" ? r.campaign_goal : undefined,
  };
}

function parseProductProfile(raw: unknown): ProductProfile {
  if (!isPlainObject(raw)) {
    return { name: "", value_prop: "" };
  }
  const r = raw;
  const valueProp =
    (typeof r.value_prop === "string" && r.value_prop) ||
    (typeof r.description === "string" && r.description) ||
    (Array.isArray(r.value_propositions)
      ? String(r.value_propositions[0] ?? "")
      : "") ||
    "";

  const diff = r.differentiators;
  const differentiators = Array.isArray(diff)
    ? diff.map((x) => String(x))
    : undefined;

  return {
    name: typeof r.name === "string" ? r.name : "",
    value_prop: valueProp,
    pricing: typeof r.pricing === "string" ? r.pricing : undefined,
    differentiators,
  };
}

function isoDate(d: unknown): string {
  if (d instanceof Date) return d.toISOString();
  if (typeof d === "string" && d.length > 0) return new Date(d).toISOString();
  return new Date().toISOString();
}

export function normalizeCampaignFromMongoDoc(
  doc: Record<string, unknown>,
): Campaign {
  const id = String(doc.campaign_id ?? doc.id ?? "");
  return {
    id,
    name: String(doc.name ?? ""),
    icp: parseIcp(doc.icp),
    product_profile: parseProductProfile(doc.product_profile),
    status: mapOrchestratorStatus(String(doc.status ?? "planning")),
    plan_id: doc.plan_id != null ? String(doc.plan_id) : undefined,
    created_at: isoDate(doc.created_at),
    counts: undefined,
  };
}

export function normalizeCampaignListRow(
  row: Record<string, unknown>,
): Campaign {
  const id = String(row.campaign_id ?? "");
  return {
    id,
    name: String(row.name ?? ""),
    icp: parseIcp(row.icp),
    product_profile: { name: "", value_prop: "" },
    status: mapOrchestratorStatus(String(row.status ?? "planning")),
    plan_id: row.plan_id != null ? String(row.plan_id) : undefined,
    created_at: isoDate(row.created_at),
    counts: undefined,
  };
}

export function normalizeCampaignDetailResponse(
  raw: Record<string, unknown>,
): Campaign {
  const nested = raw.campaign as Record<string, unknown> | undefined;
  const doc =
    nested && isPlainObject(nested) ? nested : { ...raw };
  const base = normalizeCampaignFromMongoDoc(doc);
  const status =
    typeof raw.status === "string" && raw.status.length > 0
      ? mapOrchestratorStatus(raw.status)
      : base.status;
  const plan_id =
    raw.plan_id != null ? String(raw.plan_id) : base.plan_id;
  return { ...base, status, plan_id };
}

export function defaultOrchestratorConfig(): OrchestratorCampaignCreatePayload["config"] {
  const provider =
    import.meta.env.VITE_EMAIL_ACCOUNT_PROVIDER === "microsoft"
      ? "microsoft"
      : "gmail";

  return {
    email_account: {
      provider,
      credentials_ref:
        import.meta.env.VITE_EMAIL_CREDENTIALS_REF ?? "dev-local-credentials",
    },
    min_icp_score: Number(import.meta.env.VITE_MIN_ICP_SCORE ?? 0),
    freshness_days: Number(import.meta.env.VITE_FRESHNESS_DAYS ?? 14),
    max_drafts: Number(import.meta.env.VITE_MAX_DRAFTS ?? 50),
  };
}

export function buildOrchestratorCreatePayload(
  name: string,
  icp: ICP,
  product_profile: ProductProfile,
  stackIncludes: string[],
): OrchestratorCampaignCreatePayload {
  const [minEmp, maxEmp] = icp.employee_range;
  return {
    name,
    icp: {
      industries: icp.industry ? [icp.industry] : [],
      industry: icp.industry,
      employee_count_range: { min: minEmp, max: maxEmp },
      tech_stack: stackIncludes,
      geographies: icp.geography,
      pain: icp.pain,
      additional_comment: icp.additional_comment,
      campaign_goal: icp.campaign_goal,
    },
    product_profile: {
      name: product_profile.name,
      description: product_profile.value_prop,
      differentiators: product_profile.differentiators,
    },
    config: defaultOrchestratorConfig(),
  };
}
