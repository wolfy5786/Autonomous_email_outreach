import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { endpoints } from "@/api/endpoints";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

const SERVICE_COLORS: Record<string, string> = {
  orchestrator: "#8b5cf6",
  planning: "#6366f1",
  sourcing: "#0ea5e9",
  prospecting: "#06b6d4",
  messaging: "#f59e0b",
  gateway: "#a3a3a3",
};
const DEFAULT_COLOR = "#737373";

const WINDOWS: Array<{ label: string; seconds: number }> = [
  { label: "15m", seconds: 900 },
  { label: "1h", seconds: 3600 },
  { label: "6h", seconds: 21600 },
  { label: "24h", seconds: 86400 },
];

const PHASE_BADGE: Record<string, "info" | "success" | "destructive" | "secondary"> = {
  start: "info",
  end: "success",
  error: "destructive",
  emit: "secondary",
};

/**
 * Datadog-style observability dashboard. Works global (no campaignId) and
 * scoped to a single campaign (campaignId set). All queries auto-refresh.
 */
export function ObservabilityDashboard({
  campaignId,
  defaultWindowSec = 3600,
  showActiveCampaignsTile = true,
}: {
  campaignId?: string;
  defaultWindowSec?: number;
  showActiveCampaignsTile?: boolean;
}) {
  const [windowSec, setWindowSec] = useState(defaultWindowSec);
  const [serviceFilter, setServiceFilter] = useState<string | null>(null);

  const statsQuery = useQuery({
    queryKey: ["obs-stats", windowSec, campaignId ?? "global"],
    queryFn: () => endpoints.getObservabilityStats(windowSec, campaignId),
    refetchInterval: 10_000,
  });

  const eventsQuery = useQuery({
    queryKey: ["obs-events", serviceFilter, campaignId ?? "global"],
    queryFn: () =>
      endpoints.getObservabilityEvents(200, {
        service: serviceFilter ?? undefined,
        campaignId,
      }),
    refetchInterval: 5_000,
  });

  const stats = statsQuery.data;
  const services = stats?.services ?? [];
  const serviceKeys = services.map((s) => s.service);

  const chartData = useMemo(() => {
    if (!stats) return [];
    return stats.buckets.map((b) => {
      const row: Record<string, number | string> = {
        ts: b.ts,
        label: shortTimeLabel(b.ts, windowSec),
      };
      for (const k of serviceKeys) {
        row[k] = b.by_service[k] ?? 0;
      }
      return row;
    });
  }, [stats, serviceKeys, windowSec]);

  const errorRatePct = stats ? (stats.error_rate * 100).toFixed(1) : "—";
  const deltaPct = useMemo(() => {
    if (!stats || stats.events_count_prev === 0) return null;
    return Math.round(
      ((stats.events_count - stats.events_count_prev) /
        stats.events_count_prev) *
        100,
    );
  }, [stats]);
  const slowestService = services
    .filter((s) => s.p95_ms != null)
    .sort((a, b) => (b.p95_ms ?? 0) - (a.p95_ms ?? 0))[0];

  return (
    <div className="space-y-6">
      {/* Window selector + live indicator */}
      <div className="flex items-center justify-end gap-3">
        <LiveIndicator />
        <div className="inline-flex rounded-md border border-black/10 bg-white p-0.5 text-xs">
          {WINDOWS.map((w) => (
            <button
              key={w.seconds}
              onClick={() => setWindowSec(w.seconds)}
              className={cn(
                "px-2.5 py-1 rounded transition-colors",
                windowSec === w.seconds
                  ? "bg-black text-white"
                  : "text-black/60 hover:text-black",
              )}
            >
              {w.label}
            </button>
          ))}
        </div>
      </div>

      {/* Stat tiles */}
      <div
        className={cn(
          "grid grid-cols-2 gap-3",
          showActiveCampaignsTile ? "md:grid-cols-4" : "md:grid-cols-3",
        )}
      >
        <StatTile
          label="Events"
          value={stats?.events_count}
          loading={statsQuery.isLoading}
          sub={
            deltaPct == null
              ? `last ${windowLabel(windowSec)}`
              : `${deltaPct > 0 ? "+" : ""}${deltaPct}% vs prev`
          }
          subTone={deltaPct == null ? "neutral" : deltaPct >= 0 ? "good" : "bad"}
        />
        <StatTile
          label="Error rate"
          value={stats ? `${errorRatePct}%` : undefined}
          loading={statsQuery.isLoading}
          sub={stats ? `${stats.error_count} errors` : ""}
          subTone={
            stats == null
              ? "neutral"
              : stats.error_rate === 0
                ? "good"
                : stats.error_rate < 0.05
                  ? "warn"
                  : "bad"
          }
        />
        <StatTile
          label="Slowest p95"
          value={
            slowestService?.p95_ms != null
              ? formatDuration(slowestService.p95_ms)
              : "—"
          }
          loading={statsQuery.isLoading}
          sub={slowestService?.service ?? ""}
          subTone="neutral"
        />
        {showActiveCampaignsTile && (
          <StatTile
            label="Active campaigns"
            value={stats?.active_campaigns}
            loading={statsQuery.isLoading}
            sub="with traffic in window"
            subTone="neutral"
          />
        )}
      </div>

      {/* Events over time */}
      <Section title={`Events over time · last ${windowLabel(windowSec)}`}>
        <div className="h-56">
          {statsQuery.isLoading ? (
            <Skeleton className="h-full w-full" />
          ) : chartData.length === 0 ? (
            <p className="h-full flex items-center justify-center text-sm text-black/40">
              No events in window.
            </p>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart
                data={chartData}
                margin={{ top: 8, right: 12, left: 0, bottom: 0 }}
              >
                <defs>
                  {serviceKeys.map((s) => {
                    const color = SERVICE_COLORS[s] ?? DEFAULT_COLOR;
                    return (
                      <linearGradient
                        key={s}
                        id={`grad-${s}-${campaignId ?? "global"}`}
                        x1="0"
                        y1="0"
                        x2="0"
                        y2="1"
                      >
                        <stop offset="0%" stopColor={color} stopOpacity={0.6} />
                        <stop offset="100%" stopColor={color} stopOpacity={0} />
                      </linearGradient>
                    );
                  })}
                </defs>
                <CartesianGrid
                  vertical={false}
                  strokeDasharray="2 4"
                  stroke="rgba(0,0,0,0.08)"
                />
                <XAxis
                  dataKey="label"
                  tick={{ fontSize: 11, fill: "rgba(0,0,0,0.4)" }}
                  axisLine={false}
                  tickLine={false}
                  minTickGap={28}
                />
                <YAxis
                  width={28}
                  tick={{ fontSize: 11, fill: "rgba(0,0,0,0.4)" }}
                  axisLine={false}
                  tickLine={false}
                  allowDecimals={false}
                />
                <Tooltip
                  contentStyle={{
                    fontSize: 12,
                    borderRadius: 8,
                    border: "1px solid rgba(0,0,0,0.1)",
                  }}
                />
                {serviceKeys.map((s) => (
                  <Area
                    key={s}
                    type="monotone"
                    dataKey={s}
                    stackId="1"
                    stroke={SERVICE_COLORS[s] ?? DEFAULT_COLOR}
                    strokeWidth={1.5}
                    fill={`url(#grad-${s}-${campaignId ?? "global"})`}
                  />
                ))}
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>
        {services.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            <FilterChip
              active={serviceFilter == null}
              onClick={() => setServiceFilter(null)}
            >
              All services
            </FilterChip>
            {services.map((s) => (
              <FilterChip
                key={s.service}
                active={serviceFilter === s.service}
                onClick={() =>
                  setServiceFilter(
                    serviceFilter === s.service ? null : s.service,
                  )
                }
                dot={SERVICE_COLORS[s.service] ?? DEFAULT_COLOR}
              >
                {s.service}
                <span className="ml-1 text-black/40 tabular-nums">
                  {s.events}
                </span>
              </FilterChip>
            ))}
          </div>
        )}
      </Section>

      {/* Service breakdown */}
      <Section title="Service breakdown">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-black/40 text-xs uppercase tracking-wide">
              <th className="font-medium py-2">Service</th>
              <th className="font-medium py-2 text-right">Events</th>
              <th className="font-medium py-2 text-right">Errors</th>
              <th className="font-medium py-2 text-right">Error %</th>
              <th className="font-medium py-2 text-right">p95</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-black/5">
            {statsQuery.isLoading && (
              <>
                {[0, 1, 2].map((i) => (
                  <tr key={i}>
                    {Array.from({ length: 5 }).map((_, j) => (
                      <td key={j} className="py-3">
                        <Skeleton className="h-4 w-20" />
                      </td>
                    ))}
                  </tr>
                ))}
              </>
            )}
            {!statsQuery.isLoading && services.length === 0 && (
              <tr>
                <td
                  colSpan={5}
                  className="py-6 text-sm text-black/40 text-center"
                >
                  No service activity in window.
                </td>
              </tr>
            )}
            {services.map((s) => (
              <tr key={s.service}>
                <td className="py-3">
                  <span className="inline-flex items-center gap-2">
                    <span
                      className="size-2 rounded-full"
                      style={{
                        background:
                          SERVICE_COLORS[s.service] ?? DEFAULT_COLOR,
                      }}
                    />
                    <span className="font-medium">{s.service}</span>
                  </span>
                </td>
                <td className="py-3 text-right tabular-nums">{s.events}</td>
                <td
                  className={cn(
                    "py-3 text-right tabular-nums",
                    s.errors > 0 && "text-red-600",
                  )}
                >
                  {s.errors}
                </td>
                <td className="py-3 text-right tabular-nums">
                  {s.events > 0
                    ? `${((s.errors / s.events) * 100).toFixed(1)}%`
                    : "—"}
                </td>
                <td className="py-3 text-right tabular-nums">
                  {s.p95_ms != null ? formatDuration(s.p95_ms) : "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>

      {/* Recent events live tail */}
      <Section
        title={
          <span className="inline-flex items-center gap-2">
            Recent events
            {serviceFilter && (
              <Badge variant="outline">
                service: {serviceFilter}
                <button
                  className="ml-1.5 text-black/50 hover:text-black"
                  onClick={() => setServiceFilter(null)}
                >
                  ×
                </button>
              </Badge>
            )}
          </span>
        }
      >
        <div className="max-h-[60vh] overflow-y-auto -mx-5">
          <table className="w-full text-sm">
            <thead className="text-left text-black/40 text-xs uppercase tracking-wide bg-white sticky top-0">
              <tr>
                <th className="font-medium px-5 py-2">Time</th>
                <th className="font-medium px-3 py-2">Service</th>
                <th className="font-medium px-3 py-2">Event</th>
                <th className="font-medium px-3 py-2">Phase</th>
                <th className="font-medium px-3 py-2 text-right">Duration</th>
                {!campaignId && (
                  <th className="font-medium px-5 py-2">Campaign</th>
                )}
              </tr>
            </thead>
            <tbody className="divide-y divide-black/5">
              {eventsQuery.isLoading && (
                <>
                  {[0, 1, 2, 3, 4].map((i) => (
                    <tr key={i}>
                      {Array.from({ length: campaignId ? 5 : 6 }).map((_, j) => (
                        <td key={j} className="px-3 py-2.5">
                          <Skeleton className="h-3.5 w-20" />
                        </td>
                      ))}
                    </tr>
                  ))}
                </>
              )}
              {!eventsQuery.isLoading &&
                (eventsQuery.data ?? []).map((e) => (
                  <tr
                    key={e.id}
                    className={cn(
                      "hover:bg-black/[0.02]",
                      e.phase === "error" && "bg-red-50/40",
                    )}
                  >
                    <td className="px-5 py-2.5 text-xs text-black/60 tabular-nums whitespace-nowrap">
                      {e.timestamp ? formatClock(e.timestamp) : "—"}
                    </td>
                    <td className="px-3 py-2.5">
                      <span className="inline-flex items-center gap-1.5 text-xs">
                        <span
                          className="size-2 rounded-full"
                          style={{
                            background:
                              SERVICE_COLORS[e.service ?? ""] ?? DEFAULT_COLOR,
                          }}
                        />
                        <span className="font-medium">{e.service ?? "—"}</span>
                      </span>
                    </td>
                    <td className="px-3 py-2.5 font-mono text-xs truncate max-w-[260px]">
                      {e.event_name ?? "—"}
                    </td>
                    <td className="px-3 py-2.5">
                      <Badge
                        variant={PHASE_BADGE[e.phase ?? "emit"] ?? "secondary"}
                      >
                        {e.phase ?? "emit"}
                      </Badge>
                    </td>
                    <td
                      className={cn(
                        "px-3 py-2.5 text-right tabular-nums text-xs",
                        e.duration_ms != null && e.duration_ms > 10_000
                          ? "text-amber-700"
                          : "text-black/60",
                      )}
                    >
                      {e.duration_ms != null
                        ? formatDuration(e.duration_ms)
                        : "—"}
                    </td>
                    {!campaignId && (
                      <td className="px-5 py-2.5 text-xs">
                        {e.campaign_id ? (
                          <Link
                            to={`/app/campaigns/${e.campaign_id}`}
                            className="font-mono text-black/60 hover:text-black hover:underline"
                            title={e.campaign_id}
                          >
                            {e.campaign_id.slice(0, 8)}…
                          </Link>
                        ) : (
                          <span className="text-black/30">—</span>
                        )}
                      </td>
                    )}
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </Section>
    </div>
  );
}

function Section({
  title,
  children,
}: {
  title: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-black/10 bg-white p-5">
      <h2 className="text-sm uppercase tracking-wide text-black/40 mb-3">
        {title}
      </h2>
      {children}
    </div>
  );
}

function StatTile({
  label,
  value,
  sub,
  subTone,
  loading,
}: {
  label: string;
  value?: number | string;
  sub?: string;
  subTone?: "good" | "bad" | "warn" | "neutral";
  loading?: boolean;
}) {
  const subColor =
    subTone === "good"
      ? "text-emerald-600"
      : subTone === "bad"
        ? "text-red-600"
        : subTone === "warn"
          ? "text-amber-600"
          : "text-black/40";
  return (
    <div className="rounded-xl border border-black/10 bg-white p-5">
      <div className="text-xs uppercase tracking-wide text-black/40">
        {label}
      </div>
      {loading ? (
        <Skeleton className="mt-3 h-7 w-20" />
      ) : (
        <div className="mt-2 text-2xl font-semibold tabular-nums">
          {value ?? "—"}
        </div>
      )}
      {sub && (
        <div className={cn("mt-1 text-xs tabular-nums", subColor)}>{sub}</div>
      )}
    </div>
  );
}

function FilterChip({
  active,
  onClick,
  children,
  dot,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
  dot?: string;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs transition-colors border",
        active
          ? "bg-black text-white border-black"
          : "bg-white text-black/70 border-black/10 hover:border-black/30",
      )}
    >
      {dot && (
        <span className="size-2 rounded-full" style={{ background: dot }} />
      )}
      {children}
    </button>
  );
}

function LiveIndicator() {
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-black/50">
      <span className="relative flex size-2">
        <span className="absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75 animate-ping" />
        <span className="relative inline-flex size-2 rounded-full bg-emerald-500" />
      </span>
      live
    </span>
  );
}

function shortTimeLabel(ts: string, windowSec: number): string {
  const d = new Date(ts);
  if (windowSec <= 86400) {
    return d.toLocaleTimeString(undefined, {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
  }
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function windowLabel(seconds: number): string {
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`;
  if (seconds < 86400) return `${Math.round(seconds / 3600)}h`;
  return `${Math.round(seconds / 86400)}d`;
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
  if (ms < 3_600_000) return `${(ms / 60_000).toFixed(1)}m`;
  return `${(ms / 3_600_000).toFixed(1)}h`;
}

function formatClock(ts: string): string {
  return new Date(ts).toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}
