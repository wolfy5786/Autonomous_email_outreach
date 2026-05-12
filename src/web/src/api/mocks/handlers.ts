/**
 * MSW request handlers. Mirror the endpoints defined in api/endpoints.ts.
 * Keep in sync with that file when the gateway contract grows.
 */

import { HttpResponse, http } from "msw";

import type {
  Campaign,
  CampaignCreateRequest,
  Draft,
} from "../types";
import { seed } from "./seed";

// MSW operates on the runtime URL. Vite proxies absolute paths; relative /api/*
// requests hit the same origin. We intercept both.
const url = (path: string) => path;

const draftMutations = new Map<string, Partial<Draft>>();
const newCampaigns: Campaign[] = [];

export const handlers = [
  // Campaigns ──────────────────────────────────────────────
  http.get(url("/api/campaigns"), () => {
    return HttpResponse.json([...newCampaigns, ...seed.campaigns]);
  }),

  http.get(url("/api/campaigns/:id"), ({ params }) => {
    const id = params.id as string;
    const found =
      newCampaigns.find((c) => c.id === id) ??
      seed.campaigns.find((c) => c.id === id);
    if (!found) return HttpResponse.json({ detail: "not found" }, { status: 404 });
    return HttpResponse.json(found);
  }),

  http.post(url("/api/campaigns"), async ({ request }) => {
    const body = (await request.json()) as CampaignCreateRequest;
    const created: Campaign = {
      id: `c-new-${Math.random().toString(36).slice(2, 8)}`,
      name: body.name,
      icp: body.icp,
      product_profile: body.product_profile,
      status: "planning",
      created_at: new Date().toISOString(),
      counts: { companies: 0, pocs: 0, drafts: 0 },
    };
    newCampaigns.unshift(created);
    return HttpResponse.json(created, { status: 201 });
  }),

  http.get(url("/api/campaigns/:id/companies"), ({ params }) => {
    const id = params.id as string;
    return HttpResponse.json(seed.companiesByCampaign[id] ?? []);
  }),

  http.get(url("/api/campaigns/:id/drafts"), ({ params }) => {
    const id = params.id as string;
    const base = seed.draftsByCampaign[id] ?? [];
    return HttpResponse.json(
      base.map((d) => ({ ...d, ...(draftMutations.get(d.id) ?? {}) })),
    );
  }),

  http.get(url("/api/campaigns/:id/timeline"), ({ params }) => {
    const id = params.id as string;
    const events = seed.timelinesByCampaign[id] ?? [];
    return HttpResponse.json(events);
  }),

  // Companies / POCs ───────────────────────────────────────
  http.get(url("/api/companies/:id"), ({ params }) => {
    const id = params.id as string;
    const all = Object.values(seed.companiesByCampaign).flat();
    const company = all.find((c) => c.id === id);
    if (!company)
      return HttpResponse.json({ detail: "not found" }, { status: 404 });
    return HttpResponse.json(company);
  }),

  // Drafts ─────────────────────────────────────────────────
  http.get(url("/api/drafts/:id"), ({ params }) => {
    const id = params.id as string;
    const draft = Object.values(seed.draftsByCampaign)
      .flat()
      .find((d) => d.id === id);
    if (!draft)
      return HttpResponse.json({ detail: "not found" }, { status: 404 });
    return HttpResponse.json({ ...draft, ...(draftMutations.get(id) ?? {}) });
  }),

  http.patch(url("/api/drafts/:id"), async ({ params, request }) => {
    const id = params.id as string;
    const patch = (await request.json()) as Partial<Draft>;
    const existing = Object.values(seed.draftsByCampaign)
      .flat()
      .find((d) => d.id === id);
    if (!existing)
      return HttpResponse.json({ detail: "not found" }, { status: 404 });
    const merged = { ...existing, ...(draftMutations.get(id) ?? {}), ...patch };
    draftMutations.set(id, { ...(draftMutations.get(id) ?? {}), ...patch });
    return HttpResponse.json(merged);
  }),

  // Landing ───────────────────────────────────────────────
  http.post(url("/api/early-access"), async ({ request }) => {
    const { email } = (await request.json()) as { email: string };
    if (!email || !email.includes("@")) {
      return HttpResponse.json(
        { detail: "invalid email" },
        { status: 400 },
      );
    }
    // eslint-disable-next-line no-console
    console.info("[mock] early access requested:", email);
    return HttpResponse.json({ ok: true });
  }),
];
