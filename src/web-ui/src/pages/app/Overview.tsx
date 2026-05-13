import { Link } from "react-router-dom";
import { useQueries, useQuery } from "@tanstack/react-query";
import { Activity, Building2, Mail, Users } from "lucide-react";

import { endpoints } from "@/api/endpoints";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  campaignStatusLabel,
  campaignStatusVariant,
} from "@/lib/campaign-status";
import { formatDateTime } from "@/lib/format";

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
