import { useMemo } from "react";
import { Link } from "react-router-dom";
import { useQueries, useQuery } from "@tanstack/react-query";
import { Activity, Building2, Mail, Users } from "lucide-react";
import {
  Area,
  AreaChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
} from "recharts";

import { endpoints } from "@/api/endpoints";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  campaignStatusLabel,
  campaignStatusVariant,
} from "@/lib/campaign-status";
import { formatDateTime } from "@/lib/format";
import type { CampaignStatus } from "@/api/types";

export default function Overview() {
  const statusQuery = useQuery({
    queryKey: ["status"],
    queryFn: () => endpoints.getStatus(),
    refetchInterval: 10_000,
  });

  const campaignsQuery = useQuery({
    queryKey: ["campaigns"],
    queryFn: () => endpoints.listCampaigns(),
  });

  // Aggregate companies + drafts across all campaigns for the totals.
  const companiesQueries = useQueries({
    queries: (campaignsQuery.data ?? []).map((c) => ({
      queryKey: ["campaign-companies", c.id],
      queryFn: () => endpoints.listCampaignCompanies(c.id),
      enabled: !!campaignsQuery.data,
    })),
  });
  const draftsQueries = useQueries({
    queries: (campaignsQuery.data ?? []).map((c) => ({
      queryKey: ["campaign-drafts", c.id],
      queryFn: () => endpoints.listCampaignDrafts(c.id),
      enabled: !!campaignsQuery.data,
    })),
  });
  const prospectsQueries = useQueries({
    queries: (campaignsQuery.data ?? []).map((c) => ({
      queryKey: ["campaign-prospects", c.id],
      queryFn: () => endpoints.listCampaignProspects(c.id),
      enabled: !!campaignsQuery.data,
    })),
  });

  const totals = {
    companies: companiesQueries.reduce(
      (sum, q) => sum + (q.data?.length ?? 0),
      0,
    ),
    drafts: draftsQueries.reduce((sum, q) => sum + (q.data?.length ?? 0), 0),
    prospects: prospectsQueries.reduce(
      (sum, q) => sum + (q.data?.count ?? 0),
      0,
    ),
  };

  const activeCampaigns = statusQuery.data?.campaigns.active_pipeline ?? 0;
  const completedCampaigns = statusQuery.data?.campaigns.completed ?? 0;

  // 5 most recent campaigns
  const recentCampaigns = (campaignsQuery.data ?? [])
    .slice()
    .sort((a, b) => (a.created_at < b.created_at ? 1 : -1))
    .slice(0, 5);

  // Drafts written per day for the last 7 days (sparkline).
  const draftsPerDay = useMemo(() => {
    const days: { day: string; label: string; count: number }[] = [];
    for (let i = 6; i >= 0; i -= 1) {
      const d = new Date();
      d.setHours(0, 0, 0, 0);
      d.setDate(d.getDate() - i);
      days.push({
        day: d.toISOString().slice(0, 10),
        label: d.toLocaleDateString(undefined, {
          month: "short",
          day: "numeric",
        }),
        count: 0,
      });
    }
    const byDay = new Map(days.map((d) => [d.day, d]));
    for (const q of draftsQueries) {
      for (const draft of q.data ?? []) {
        const key = (draft.generated_at ?? "").slice(0, 10);
        const bucket = byDay.get(key);
        if (bucket) bucket.count += 1;
      }
    }
    return days;
  }, [draftsQueries]);

  // Campaigns by status (donut).
  const statusBreakdown = useMemo(() => {
    const by = statusQuery.data?.campaigns.by_status ?? {};
    const COLORS: Record<string, string> = {
      planning: "#6366f1",
      sourcing: "#3b82f6",
      prospecting: "#0ea5e9",
      messaging: "#f59e0b",
      completed: "#10b981",
      paused: "#a3a3a3",
      failed: "#ef4444",
      cancelled: "#737373",
    };
    return Object.entries(by)
      .filter(([, v]) => v > 0)
      .map(([k, v]) => ({
        name: campaignStatusLabel(k as CampaignStatus),
        value: v,
        fill: COLORS[k] ?? "#737373",
      }));
  }, [statusQuery.data]);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Overview</h1>
        <p className="mt-2 text-black/60">
          Pipeline at a glance.
        </p>
      </div>

      {/* Stat tiles */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatTile
          icon={<Activity className="size-4" />}
          label="Active campaigns"
          value={activeCampaigns}
          sub={`${completedCampaigns} completed`}
        />
        <StatTile
          icon={<Building2 className="size-4" />}
          label="Companies sourced"
          value={totals.companies}
          loading={companiesQueries.some((q) => q.isLoading)}
        />
        <StatTile
          icon={<Users className="size-4" />}
          label="Prospects ranked"
          value={totals.prospects}
          loading={prospectsQueries.some((q) => q.isLoading)}
        />
        <StatTile
          icon={<Mail className="size-4" />}
          label="Drafts written"
          value={totals.drafts}
          loading={draftsQueries.some((q) => q.isLoading)}
        />
      </div>

      {/* Charts */}
      <div className="grid md:grid-cols-3 gap-3">
        <div className="md:col-span-2 rounded-xl border border-black/10 bg-white p-5">
          <div className="flex items-baseline justify-between">
            <h2 className="text-sm uppercase tracking-wide text-black/40">
              Drafts last 7 days
            </h2>
            <span className="text-xs text-black/40 tabular-nums">
              {draftsPerDay.reduce((s, d) => s + d.count, 0)} total
            </span>
          </div>
          <div className="mt-3 h-32">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart
                data={draftsPerDay}
                margin={{ top: 5, right: 5, left: 0, bottom: 0 }}
              >
                <defs>
                  <linearGradient id="draftFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#10b981" stopOpacity={0.35} />
                    <stop offset="100%" stopColor="#10b981" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis
                  dataKey="label"
                  tick={{ fontSize: 11, fill: "rgba(0,0,0,0.4)" }}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip
                  cursor={{ stroke: "rgba(0,0,0,0.1)" }}
                  contentStyle={{
                    fontSize: 12,
                    borderRadius: 8,
                    border: "1px solid rgba(0,0,0,0.1)",
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="count"
                  stroke="#10b981"
                  strokeWidth={2}
                  fill="url(#draftFill)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="rounded-xl border border-black/10 bg-white p-5">
          <h2 className="text-sm uppercase tracking-wide text-black/40">
            By status
          </h2>
          <div className="mt-3 h-32">
            {statusBreakdown.length === 0 ? (
              <p className="h-full flex items-center justify-center text-xs text-black/40">
                No campaigns yet
              </p>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Tooltip
                    contentStyle={{
                      fontSize: 12,
                      borderRadius: 8,
                      border: "1px solid rgba(0,0,0,0.1)",
                    }}
                  />
                  <Pie
                    data={statusBreakdown}
                    dataKey="value"
                    nameKey="name"
                    innerRadius={28}
                    outerRadius={52}
                    paddingAngle={2}
                  >
                    {statusBreakdown.map((s, i) => (
                      <Cell key={i} fill={s.fill} />
                    ))}
                  </Pie>
                </PieChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
      </div>

      {/* Recent campaigns */}
      <div className="rounded-xl border border-black/10 bg-white overflow-hidden">
        <div className="px-5 py-3 border-b border-black/5 flex items-center justify-between">
          <h2 className="text-sm uppercase tracking-wide text-black/40">
            Recent campaigns
          </h2>
          <Link
            to="/app/campaigns"
            className="text-xs text-black/50 hover:text-black"
          >
            View all →
          </Link>
        </div>
        {campaignsQuery.isLoading ? (
          <div className="p-5 space-y-2">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        ) : recentCampaigns.length === 0 ? (
          <p className="p-8 text-sm text-black/50 italic text-center">
            No campaigns yet. Create one from the Campaigns page.
          </p>
        ) : (
          <ul className="divide-y divide-black/5">
            {recentCampaigns.map((c) => (
              <li key={c.id}>
                <Link
                  to={`/app/campaigns/${c.id}`}
                  className="flex items-center justify-between gap-3 px-5 py-3 hover:bg-black/[0.02]"
                >
                  <div className="min-w-0">
                    <div className="font-medium truncate">{c.name}</div>
                    <div className="text-xs text-black/40 font-mono truncate">
                      {c.id}
                    </div>
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    <span className="text-xs text-black/40">
                      {formatDateTime(c.created_at)}
                    </span>
                    <Badge variant={campaignStatusVariant(c.status)}>
                      {campaignStatusLabel(c.status)}
                    </Badge>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function StatTile({
  icon,
  label,
  value,
  sub,
  loading,
}: {
  icon: React.ReactNode;
  label: string;
  value: number | string;
  sub?: string;
  loading?: boolean;
}) {
  return (
    <div className="rounded-xl border border-black/10 bg-white p-5">
      <div className="flex items-center gap-2 text-xs uppercase tracking-wide text-black/40">
        {icon}
        {label}
      </div>
      {loading ? (
        <Skeleton className="mt-3 h-8 w-16" />
      ) : (
        <div className="mt-3 text-3xl font-semibold tabular-nums">{value}</div>
      )}
      {sub && (
        <div className="mt-1 text-xs text-black/40 tabular-nums">{sub}</div>
      )}
    </div>
  );
}
