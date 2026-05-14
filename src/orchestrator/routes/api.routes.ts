import { Router, Request, Response, NextFunction } from 'express';
import { Campaign, EmailDraft } from '../../shared/models';
import { AppError } from '../middleware/error-handler';
import { CampaignStatusRepository } from '../postgres';

/**
 * Top-level `/api/*` routes from design_docs/orchestrator_service_role.md (sections 3.2–3.4)
 * (campaign routes live under `/api/campaigns` via campaign.routes.ts).
 */
export function createApiRouter(statusRepo: CampaignStatusRepository): Router {
  const router = Router();

  // GET /api/status — Service status (Postgres-backed campaign counts per §2.1).
  router.get('/status', async (_req: Request, res: Response, next: NextFunction) => {
    try {
      const counts = await statusRepo.countByStatus();
      const PIPELINE_ACTIVE = ['planning', 'sourcing', 'prospecting', 'messaging'];
      const active_pipeline = PIPELINE_ACTIVE.reduce(
        (sum, s) => sum + (counts[s] ?? 0),
        0
      );

      res.json({
        service: 'orchestrator',
        uptime_seconds: Math.floor(process.uptime()),
        campaigns: {
          active_pipeline,
          in_messaging: counts['messaging'] ?? 0,
          completed: counts['completed'] ?? 0,
          paused: counts['paused'] ?? 0,
          cancelled: counts['cancelled'] ?? 0,
          failed: counts['failed'] ?? 0,
          by_status: counts,
        },
        queues: {
          note: 'Queue depth / DLQ metrics require broker integration (stub)',
          depths: null,
          dlq_total: null,
        },
        timestamp: new Date().toISOString(),
      });
    } catch (err) {
      next(err);
    }
  });

  // GET /api/prospects/:id — Prospect detail joined across campaigns and drafts.
  router.get('/prospects/:id', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const poc_id = String(req.params.id);

      // A poc_id can appear in multiple campaigns; return all matches.
      const campaigns = await Campaign.find({
        'pipeline_state.ranked_prospect_ids': poc_id,
      })
        .select('campaign_id name pipeline_state.ranked_prospect_scores config.min_icp_score')
        .lean();

      if (campaigns.length === 0) {
        throw new AppError(404, 'Prospect not found in any campaign');
      }

      const drafts = await EmailDraft.find({ poc_id })
        .select('draft_id campaign_id status generated_at')
        .lean();

      res.json({
        poc_id,
        campaigns: campaigns.map((c) => ({
          campaign_id: c.campaign_id,
          name: c.name,
          score: c.pipeline_state?.ranked_prospect_scores?.[poc_id] ?? null,
          min_icp_score: c.config?.min_icp_score ?? null,
        })),
        drafts,
      });
    } catch (err) {
      next(err);
    }
  });

  // ── Observability ──────────────────────────────────────────────
  // Aggregated stats + recent events across all campaigns, used by the
  // /app/observability dashboard. Reads from the trace_events collection
  // owned by the observability service.

  // GET /api/observability/stats?window=3600
  // Returns counts/durations for the configured window, grouped by service,
  // plus per-minute buckets for the events-over-time chart.
  router.get(
    '/observability/stats',
    async (req: Request, res: Response, next: NextFunction) => {
      try {
        const db = EmailDraft.db.db;
        if (!db) {
          res.json({ window_seconds: 0, events_count: 0, services: [], buckets: [] });
          return;
        }
        const windowSec = Math.max(
          60,
          Math.min(parseInt(String(req.query.window ?? '3600'), 10) || 3600, 86400),
        );
        const now = Date.now();
        const since = new Date(now - windowSec * 1000);
        const prevSince = new Date(now - 2 * windowSec * 1000);

        const campaignId = req.query.campaign_id
          ? String(req.query.campaign_id)
          : null;
        const baseFilter: Record<string, unknown> = campaignId
          ? { campaign_id: campaignId }
          : {};

        const events = await db
          .collection('trace_events')
          .find({ ...baseFilter, timestamp: { $gte: since } })
          .project({
            timestamp: 1,
            service: 1,
            phase: 1,
            duration_ms: 1,
            campaign_id: 1,
          })
          .limit(5000)
          .toArray();

        const prevCount = await db
          .collection('trace_events')
          .countDocuments({
            ...baseFilter,
            timestamp: { $gte: prevSince, $lt: since },
          });

        // Per-service rollup.
        type ServiceAgg = {
          service: string;
          events: number;
          errors: number;
          durations: number[];
        };
        const byService = new Map<string, ServiceAgg>();
        const activeCampaigns = new Set<string>();
        let errors = 0;
        for (const e of events) {
          const svc = String(e.service ?? 'unknown');
          const agg =
            byService.get(svc) ??
            ({ service: svc, events: 0, errors: 0, durations: [] } as ServiceAgg);
          agg.events += 1;
          if (e.phase === 'error') agg.errors += 1;
          if (typeof e.duration_ms === 'number') agg.durations.push(e.duration_ms);
          byService.set(svc, agg);
          if (e.phase === 'error') errors += 1;
          if (e.campaign_id) activeCampaigns.add(String(e.campaign_id));
        }

        const services = Array.from(byService.values())
          .map((a) => ({
            service: a.service,
            events: a.events,
            errors: a.errors,
            p95_ms: percentile(a.durations, 0.95),
            avg_ms: a.durations.length
              ? Math.round(a.durations.reduce((s, x) => s + x, 0) / a.durations.length)
              : null,
          }))
          .sort((a, b) => b.events - a.events);

        // Per-minute buckets, keyed by ISO minute. Build a continuous range so the
        // chart shows zero-value gaps instead of missing ticks.
        const bucketCount = Math.min(Math.ceil(windowSec / 60), 240);
        const bucketSpanMs = (windowSec * 1000) / bucketCount;
        const bucketStartMs = now - bucketCount * bucketSpanMs;
        const allServices = Array.from(byService.keys());
        const buckets: {
          ts: string;
          total: number;
          by_service: Record<string, number>;
        }[] = [];
        for (let i = 0; i < bucketCount; i += 1) {
          const start = bucketStartMs + i * bucketSpanMs;
          buckets.push({
            ts: new Date(start).toISOString(),
            total: 0,
            by_service: Object.fromEntries(allServices.map((s) => [s, 0])),
          });
        }
        for (const e of events) {
          const tMs = new Date(e.timestamp as unknown as string).getTime();
          const idx = Math.floor((tMs - bucketStartMs) / bucketSpanMs);
          if (idx < 0 || idx >= bucketCount) continue;
          buckets[idx].total += 1;
          const svc = String(e.service ?? 'unknown');
          buckets[idx].by_service[svc] = (buckets[idx].by_service[svc] ?? 0) + 1;
        }

        res.json({
          window_seconds: windowSec,
          generated_at: new Date(now).toISOString(),
          events_count: events.length,
          events_count_prev: prevCount,
          error_count: errors,
          error_rate: events.length > 0 ? errors / events.length : 0,
          active_campaigns: activeCampaigns.size,
          services,
          buckets,
        });
      } catch (err) {
        next(err);
      }
    },
  );

  // GET /api/observability/events?limit=200&service=&phase=
  // Recent trace events globally, newest first. Used by the live events table.
  router.get(
    '/observability/events',
    async (req: Request, res: Response, next: NextFunction) => {
      try {
        const db = EmailDraft.db.db;
        if (!db) {
          res.json([]);
          return;
        }
        const limit = Math.max(
          1,
          Math.min(parseInt(String(req.query.limit ?? '200'), 10) || 200, 1000),
        );
        const filter: Record<string, unknown> = {};
        if (req.query.service) filter.service = String(req.query.service);
        if (req.query.phase) filter.phase = String(req.query.phase);
        if (req.query.campaign_id)
          filter.campaign_id = String(req.query.campaign_id);

        const events = await db
          .collection('trace_events')
          .find(filter)
          .sort({ timestamp: -1 })
          .limit(limit)
          .toArray();

        res.json(
          events.map((e) => ({
            id: String(e._id),
            trace_id: e.trace_id ?? null,
            campaign_id: e.campaign_id ?? null,
            service: e.service ?? null,
            event_name: e.event_name ?? null,
            phase: e.phase ?? null,
            timestamp:
              e.timestamp instanceof Date
                ? e.timestamp.toISOString()
                : (e.timestamp ?? null),
            duration_ms: e.duration_ms ?? null,
            error_type: e.error_type ?? null,
            error_message: e.error_message ?? null,
          })),
        );
      } catch (err) {
        next(err);
      }
    },
  );

  // GET /api/companies/:id — One company with its POCs.
  router.get('/companies/:id', async (req: Request, res: Response, next: NextFunction) => {
    try {
      const db = EmailDraft.db.db;
      if (!db) throw new AppError(503, 'Database unavailable');
      const companyId = String(req.params.id);
      const c = await db.collection('companies').findOne({ _id: companyId as unknown as never });
      if (!c) throw new AppError(404, 'Company not found');
      const persons = await db
        .collection('persons')
        .find({ company_id: companyId })
        .toArray();

      // Map the canonical persons-collection rows first.
      let pocsOut = persons.map((p) => ({
        id: String(p._id),
        company_id: String(p.company_id),
        full_name:
          (p.name as string | undefined) ??
          ([p.first_name, p.last_name].filter(Boolean).join(' ').trim() || null),
        title: p.title ?? undefined,
        email: p.email ?? undefined,
        linkedin_url: p.linkedin_url ?? undefined,
        seniority: p.seniority ?? undefined,
      }));

      // Fallback: sourcing's LinkedIn POC op sometimes writes only to
      // companies.extra (poc_name / poc_title / poc_profile_url) without
      // upserting into the `persons` collection. Surface that POC so the
      // detail page isn't blank for the ~96% of records in this state.
      const extra = (c.extra ?? {}) as Record<string, unknown>;
      if (
        pocsOut.length === 0 &&
        typeof extra.poc_name === 'string' &&
        extra.poc_name.trim()
      ) {
        pocsOut = [
          {
            id: `extra-poc:${String(c._id)}`,
            company_id: String(c._id),
            full_name: extra.poc_name.trim(),
            title:
              typeof extra.poc_title === 'string' && extra.poc_title.trim()
                ? extra.poc_title
                : undefined,
            email: undefined,
            linkedin_url:
              typeof extra.poc_profile_url === 'string' &&
              extra.poc_profile_url.trim()
                ? extra.poc_profile_url
                : undefined,
            seniority: undefined,
          },
        ];
      }

      res.json({
        id: String(c._id),
        name: c.name ?? null,
        domain: c.domain ?? undefined,
        industry: c.industry ?? undefined,
        employee_count: c.employee_count ?? undefined,
        hq: c.headquarters
          ? {
              city: c.headquarters.city ?? undefined,
              country: c.headquarters.country ?? undefined,
            }
          : undefined,
        last_scrape_mode: c.scrape_mode_last ?? undefined,
        funding_stage: c.funding_stage ?? undefined,
        tech_stack: Array.isArray(c.tech_stack) ? c.tech_stack : undefined,
        description: c.description ?? undefined,
        linkedin_url: c.linkedin_url ?? undefined,
        website_url: c.website_url ?? undefined,
        icp_fit_score:
          typeof c.icp_fit_score === 'number' ? c.icp_fit_score : undefined,
        data_completeness:
          typeof c.data_completeness === 'number' ? c.data_completeness : undefined,
        freshness_timestamp: c.freshness_timestamp ?? undefined,
        campaign_ids: Array.isArray(c.campaign_ids) ? c.campaign_ids : undefined,
        enriched: typeof c.enriched === 'boolean' ? c.enriched : undefined,
        provenance: c.provenance ?? undefined,
        extra: c.extra ?? undefined,
        pocs: pocsOut,
      });
    } catch (err) {
      next(err);
    }
  });

  // GET /api/drafts/:id — One draft record, joined with recipient (POC + company)
  // so the UI can render a Gmail-style "From / To / Subject" header without
  // separate roundtrips to persons/companies.
  router.get('/drafts/:id', async (req: Request, res: Response, next: NextFunction) => {
    try {
      // Python messaging writes drafts with id = uuid (and _id = same uuid).
      // Mongoose can't query _id with a UUID (would try to cast to ObjectId),
      // so use the `id` field; fall back to `draft_id` for any future writers.
      const draftId = String(req.params.id);
      const draft = await EmailDraft.findOne({
        $or: [{ id: draftId }, { draft_id: draftId }],
      })
        .select('-__v')
        .lean();
      if (!draft) throw new AppError(404, 'Draft not found');

      // Raw collection access — persons + companies are owned by other services
      // (Beanie/Python) and not modeled in Mongoose here.
      const db = EmailDraft.db.db;
      const [poc, company] = db
        ? await Promise.all([
            db.collection('persons').findOne({ _id: draft.poc_id as unknown as never }),
            db.collection('companies').findOne({ _id: draft.company_id as unknown as never }),
          ])
        : [null, null];

      const pocName =
        (poc?.name as string | undefined) ??
        ([poc?.first_name, poc?.last_name].filter(Boolean).join(' ').trim() || null);

      res.json({
        ...draft,
        recipient: {
          name: pocName,
          email: (poc?.email as string | null) ?? null,
          company: (company?.name as string | null) ?? null,
          company_domain: (company?.domain as string | null) ?? null,
          linkedin_url: (poc?.linkedin_url as string | null) ?? null,
        },
      });
    } catch (err) {
      next(err);
    }
  });

  return router;
}

function percentile(values: number[], p: number): number | null {
  if (values.length === 0) return null;
  const sorted = [...values].sort((a, b) => a - b);
  const idx = Math.min(
    sorted.length - 1,
    Math.max(0, Math.ceil(p * sorted.length) - 1),
  );
  return Math.round(sorted[idx]);
}
