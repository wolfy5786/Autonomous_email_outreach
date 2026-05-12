/**
 * Seed data used by MSW handlers in dev. Built to reflect real shapes a working
 * pipeline would produce, with enough variety to exercise filters, empty states,
 * and the timeline view.
 */

import type {
  Campaign,
  CompanyDetail,
  Draft,
  TraceEvent,
} from "../types";

export const campaigns: Campaign[] = [
  {
    id: "c-acme-001",
    name: "Acme Observability — Q2 K8s launch",
    status: "ready_for_review",
    created_at: "2026-05-10T14:22:00Z",
    plan_id: "p-acme-001",
    icp: {
      industry: "B2B SaaS",
      employee_range: [50, 500],
      stack_includes: ["Kubernetes", "AWS"],
      geography: ["US", "EU"],
      pain: "Slow incident response and poor deploy observability",
    },
    product_profile: {
      name: "Acme Observability",
      value_prop:
        "Correlate deploys with runtime anomalies in under two minutes.",
      pricing: "usage-based",
      differentiators: ["deploy-aware", "OSS-friendly", "no agent required"],
    },
    counts: { companies: 24, pocs: 41, drafts: 18 },
  },
  {
    id: "c-bio-002",
    name: "Bioseq — academic outreach",
    status: "drafting",
    created_at: "2026-05-11T09:05:00Z",
    plan_id: "p-bio-002",
    icp: {
      industry: "Genomics research",
      employee_range: [10, 200],
      stack_includes: ["Python", "Nextflow"],
      geography: ["US"],
      pain: "Cohort recruitment for rare-disease NIH-funded studies",
    },
    product_profile: {
      name: "Bioseq",
      value_prop:
        "Faster cohort matching for rare-disease researchers, on top of existing NIH grants.",
    },
    counts: { companies: 12, pocs: 19, drafts: 7 },
  },
  {
    id: "c-edge-003",
    name: "Edgewise — Hacker News audience",
    status: "sourcing",
    created_at: "2026-05-12T16:40:00Z",
    icp: {
      industry: "Developer tools",
      employee_range: [1, 30],
      stack_includes: ["Rust", "WebAssembly"],
      geography: ["US", "EU", "APAC"],
      pain: "Cold-start latency on serverless platforms",
    },
    product_profile: {
      name: "Edgewise",
      value_prop:
        "Edge runtime that ships your Wasm in ~5ms cold-start, anywhere on Earth.",
    },
    counts: { companies: 6, pocs: 0, drafts: 0 },
  },
];

const companiesByCampaign: Record<string, CompanyDetail[]> = {
  "c-acme-001": [
    {
      id: "co-stripe",
      name: "Stripe",
      domain: "stripe.com",
      industry: "Payments / Fintech",
      employee_count: 8000,
      hq: { city: "South San Francisco", region: "CA", country: "US" },
      last_scrape_mode: "all",
      pocs: [
        {
          id: "p-stripe-maya",
          company_id: "co-stripe",
          full_name: "Maya Rodriguez",
          title: "VP of Engineering, Apps Platform",
          email: "maya@stripe.com",
          linkedin_url: "https://linkedin.com/in/mayarodriguez",
          seniority: "vp",
        },
      ],
    },
    {
      id: "co-vercel",
      name: "Vercel",
      domain: "vercel.com",
      industry: "Developer Infrastructure",
      employee_count: 480,
      hq: { city: "San Francisco", region: "CA", country: "US" },
      last_scrape_mode: "all",
      pocs: [
        {
          id: "p-vercel-arvind",
          company_id: "co-vercel",
          full_name: "Arvind Iyer",
          title: "Director of Platform",
          email: "arvind@vercel.com",
          seniority: "director",
        },
        {
          id: "p-vercel-julia",
          company_id: "co-vercel",
          full_name: "Julia Klein",
          title: "Staff SRE",
          email: "julia.klein@vercel.com",
          seniority: "staff",
        },
      ],
    },
    {
      id: "co-loom",
      name: "Loom",
      domain: "loom.com",
      industry: "Video / Collaboration",
      employee_count: 300,
      hq: { city: "San Francisco", region: "CA", country: "US" },
      last_scrape_mode: "partial",
      pocs: [
        {
          id: "p-loom-david",
          company_id: "co-loom",
          full_name: "David Park",
          title: "Head of Platform Engineering",
          email: "david@loom.com",
          seniority: "head",
        },
      ],
    },
  ],
  "c-bio-002": [
    {
      id: "co-broad",
      name: "Broad Institute",
      domain: "broadinstitute.org",
      industry: "Genomics Research",
      employee_count: 3500,
      hq: { city: "Cambridge", region: "MA", country: "US" },
      last_scrape_mode: "all",
      pocs: [
        {
          id: "p-broad-emily",
          company_id: "co-broad",
          full_name: "Dr. Emily Chen",
          title: "Director, Rare Disease Genomics",
          email: "echen@broadinstitute.org",
          seniority: "director",
        },
      ],
    },
  ],
  "c-edge-003": [],
};

const draftsByCampaign: Record<string, Draft[]> = {
  "c-acme-001": [
    {
      id: "d-stripe-maya",
      campaign_id: "c-acme-001",
      company_id: "co-stripe",
      poc_id: "p-stripe-maya",
      subject: "deploy-aware anomalies for the Stripe Apps team",
      body: `Hey Maya —

Saw the Stripe Apps SDK launch last Tuesday. The doc on webhook reliability hinted at the same thing our other K8s-shop customers ran into: when a deploy goes out at 3am, you don't find the regression until the morning. We built runtime anomaly correlation that catches it in the first 90s post-deploy.

Worth a 15-min look while the SDK is still settling? I can send our Stripe-shaped writeup either way.

— Mokshith`,
      personalization_hooks: [
        "Stripe Apps SDK launch (last Tuesday)",
        "webhook reliability mention in launch doc",
      ],
      generated_at: "2026-05-12T11:14:00Z",
      status: "draft_created",
      email_draft_ref: "r-gm-90021",
      email_provider: "gmail",
      retry_count: 0,
      llm_model: "gemini/gemini-2.5-flash",
      llm_usage: {
        prompt_tokens: 1842,
        completion_tokens: 312,
        total_tokens: 2154,
      },
    },
    {
      id: "d-vercel-arvind",
      campaign_id: "c-acme-001",
      company_id: "co-vercel",
      poc_id: "p-vercel-arvind",
      subject: "post-Next.js 15 platform deploys + anomaly detection",
      body: `Hi Arvind —

Saw the Next.js 15 GA post and Vercel's mention of edge-runtime SLO regressions during the canary. We built deploy-aware anomaly correlation that flags the 1% of canaries that look fine but break a downstream service — usually within 60-90s.

Could be interesting given how many platform teams are running Next 15 canaries against your edge. Up for a quick comparison call?

— Mokshith`,
      personalization_hooks: [
        "Next.js 15 GA blog post",
        "edge-runtime SLO regressions in canary mention",
      ],
      generated_at: "2026-05-12T11:32:00Z",
      status: "draft_created",
      email_draft_ref: "r-gm-90022",
      email_provider: "gmail",
      retry_count: 0,
      llm_model: "gemini/gemini-2.5-flash",
      llm_usage: {
        prompt_tokens: 1933,
        completion_tokens: 284,
        total_tokens: 2217,
      },
    },
    {
      id: "d-loom-david",
      campaign_id: "c-acme-001",
      company_id: "co-loom",
      poc_id: "p-loom-david",
      subject: "post-Atlassian, platform team incident response",
      body: `Hi David —

After the Atlassian acquisition I'd imagine the platform team's incident response is getting more scrutiny — there are a lot of pipes meeting now. We do deploy-aware anomaly correlation that catches the regression in the first 90s, before it hits a sev-2. Comes up a lot in M&A platform reviews.

Worth a quick look? Happy to send the post-acquisition writeup we did with two other teams either way.

— Mokshith`,
      personalization_hooks: [
        "Atlassian acquisition (recent)",
        "platform team incident response",
      ],
      generated_at: "2026-05-12T11:51:00Z",
      status: "generating",
      retry_count: 1,
      llm_model: "gemini/gemini-2.5-flash",
    },
  ],
  "c-bio-002": [
    {
      id: "d-broad-emily",
      campaign_id: "c-bio-002",
      company_id: "co-broad",
      poc_id: "p-broad-emily",
      subject: "cohort matching for the new R01 on rare neurodegenerative variants",
      body: `Dr. Chen —

Saw the R01 award land for the rare neurodegenerative variant cohort study. Recruitment timelines on these are brutal — usually 18-24 months for >500 patients. We help match patient candidates from existing biobank consents and clinical records in days rather than months.

I'd love to send the case study we did with the Mayo neurology group either way. Worth a 15-min intro?

— Mokshith`,
      personalization_hooks: [
        "R01 award (recent, NIH RePORTER)",
        "rare neurodegenerative variant cohort study",
      ],
      generated_at: "2026-05-12T18:02:00Z",
      status: "draft_created",
      email_draft_ref: "r-gm-90031",
      email_provider: "gmail",
      retry_count: 0,
      llm_model: "gemini/gemini-2.5-flash",
      llm_usage: {
        prompt_tokens: 1620,
        completion_tokens: 268,
        total_tokens: 1888,
      },
    },
  ],
  "c-edge-003": [],
};

const timelinesByCampaign: Record<string, TraceEvent[]> = {
  "c-acme-001": [
    makeEvent({
      service: "gateway",
      event_name: "campaign.created",
      phase: "emit",
      offsetMs: 0,
    }),
    makeEvent({
      service: "gateway",
      event_name: "plan.requested.publish",
      phase: "emit",
      offsetMs: 41,
    }),
    makeEvent({
      service: "planning",
      event_name: "plan.requested.consume",
      phase: "start",
      offsetMs: 80,
    }),
    makeEvent({
      service: "planning",
      event_name: "plan.ready.publish",
      phase: "emit",
      offsetMs: 102,
    }),
    makeEvent({
      service: "planning",
      event_name: "plan.requested.consume",
      phase: "end",
      offsetMs: 106,
      duration_ms: 26,
    }),
    makeEvent({
      service: "sourcing",
      event_name: "sourcing.requested.consume",
      phase: "start",
      offsetMs: 1240,
    }),
    makeEvent({
      service: "sourcing",
      event_name: "sourcing.requested.consume",
      phase: "end",
      offsetMs: 14820,
      duration_ms: 13580,
    }),
    makeEvent({
      service: "messaging",
      event_name: "messaging.requested.consume",
      phase: "start",
      offsetMs: 15500,
    }),
    makeEvent({
      service: "messaging",
      event_name: "draft.written.publish",
      phase: "emit",
      offsetMs: 18120,
    }),
    makeEvent({
      service: "messaging",
      event_name: "messaging.requested.consume",
      phase: "end",
      offsetMs: 18234,
      duration_ms: 2734,
    }),
  ],
  "c-bio-002": [],
  "c-edge-003": [],
};

function makeEvent(opts: {
  service: string;
  event_name: string;
  phase: TraceEvent["phase"];
  offsetMs: number;
  duration_ms?: number;
}): TraceEvent {
  const base = new Date("2026-05-12T19:17:51.096Z").getTime();
  return {
    id: crypto.randomUUID(),
    trace_id: "32698dfc-4de2-4a0a-8a53-146a936286e9",
    campaign_id: "c-acme-001",
    service: opts.service,
    event_name: opts.event_name,
    phase: opts.phase,
    timestamp: new Date(base + opts.offsetMs).toISOString(),
    duration_ms: opts.duration_ms ?? null,
    error_type: null,
    error_message: null,
    metadata: {},
  };
}

export const seed = {
  campaigns,
  companiesByCampaign,
  draftsByCampaign,
  timelinesByCampaign,
};
