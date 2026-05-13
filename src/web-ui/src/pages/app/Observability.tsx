import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { CampaignTimeline } from "@/components/app/CampaignTimeline";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { endpoints } from "@/api/endpoints";
import {
  campaignStatusLabel,
  campaignStatusVariant,
} from "@/lib/campaign-status";
import { formatDateTime } from "@/lib/format";
import { cn } from "@/lib/utils";

export default function Observability() {
  const { data: campaigns, isLoading } = useQuery({
    queryKey: ["campaigns"],
    queryFn: () => endpoints.listCampaigns(),
  });

  const [selectedId, setSelectedId] = useState<string | null>(null);

  // Default selection: the most recent campaign once the list loads.
  useEffect(() => {
    if (!selectedId && campaigns && campaigns.length > 0) {
      setSelectedId(campaigns[0].id);
    }
  }, [campaigns, selectedId]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Observability</h1>
        <p className="mt-2 text-black/60">
          End-to-end campaign trace timeline. Pick a campaign to view its
          stage-by-stage events.
        </p>
      </div>

      <div className="grid md:grid-cols-[320px_1fr] gap-4">
        {/* Campaign list */}
        <div className="rounded-lg border border-black/10 bg-white overflow-hidden">
          <div className="px-4 py-3 border-b border-black/5 text-xs uppercase tracking-wide text-black/40">
            Campaigns
          </div>
          {isLoading ? (
            <div className="p-4 space-y-2">
              {[0, 1, 2].map((i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : !campaigns || campaigns.length === 0 ? (
            <p className="p-4 text-sm text-black/50 italic">
              No campaigns yet.
            </p>
          ) : (
            <ul className="divide-y divide-black/5 max-h-[70vh] overflow-y-auto">
              {campaigns.map((c) => (
                <li key={c.id}>
                  <button
                    type="button"
                    onClick={() => setSelectedId(c.id)}
                    className={cn(
                      "w-full text-left px-4 py-3 hover:bg-black/[0.02]",
                      selectedId === c.id && "bg-black/[0.03]",
                    )}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-medium truncate">{c.name}</span>
                      <Badge variant={campaignStatusVariant(c.status)}>
                        {campaignStatusLabel(c.status)}
                      </Badge>
                    </div>
                    <div className="mt-1 text-xs text-black/40 font-mono truncate">
                      {c.id}
                    </div>
                    <div className="mt-0.5 text-xs text-black/40">
                      {formatDateTime(c.created_at)}
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* Timeline panel */}
        <div className="rounded-lg border border-black/10 bg-white p-5">
          {selectedId ? (
            <CampaignTimeline campaignId={selectedId} />
          ) : (
            <p className="text-sm text-black/50 italic py-8 text-center">
              Select a campaign on the left to view its trace events.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
