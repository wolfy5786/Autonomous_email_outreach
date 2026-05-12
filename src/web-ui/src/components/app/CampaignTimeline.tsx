import { useQuery } from "@tanstack/react-query";

import { endpoints } from "@/api/endpoints";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { formatDateTime } from "@/lib/format";
import { cn } from "@/lib/utils";

const PHASE_BADGE = {
  start: "info" as const,
  end: "success" as const,
  error: "destructive" as const,
  emit: "secondary" as const,
};

export function CampaignTimeline({ campaignId }: { campaignId: string }) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["campaign-timeline", campaignId],
    queryFn: () => endpoints.getCampaignTimeline(campaignId),
  });

  if (isLoading) {
    return (
      <div className="space-y-3">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-14 w-full" />
        ))}
      </div>
    );
  }
  if (isError) {
    return (
      <div className="text-sm text-red-600">
        Failed to load trace events.
      </div>
    );
  }
  if (!data || data.length === 0) {
    return (
      <div className="text-sm text-black/50 italic py-8 text-center">
        No trace events recorded yet. Events will appear as the pipeline
        processes this campaign.
      </div>
    );
  }

  return (
    <ol className="relative border-l border-black/10 ml-2 space-y-5">
      {data.map((e) => (
        <li key={e.id} className="ml-6">
          <span
            className={cn(
              "absolute -left-1.5 mt-1.5 size-3 rounded-full border-2 border-white",
              e.phase === "error"
                ? "bg-red-500"
                : e.phase === "end"
                  ? "bg-emerald-500"
                  : e.phase === "start"
                    ? "bg-indigo-500"
                    : "bg-neutral-400",
            )}
          />
          <div className="flex items-center gap-3 flex-wrap">
            <code className="text-sm font-medium">{e.event_name}</code>
            <Badge variant={PHASE_BADGE[e.phase]}>{e.phase}</Badge>
            <span className="text-xs text-black/40">{e.service}</span>
            {e.duration_ms != null && (
              <span className="text-xs text-black/40">
                {e.duration_ms} ms
              </span>
            )}
          </div>
          <div className="text-xs text-black/40 mt-1">
            {formatDateTime(e.timestamp)}
          </div>
          {e.error_message && (
            <div className="mt-1 text-xs text-red-600">
              <code>{e.error_type}</code>: {e.error_message}
            </div>
          )}
        </li>
      ))}
    </ol>
  );
}
