import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Megaphone } from "lucide-react";

import { endpoints } from "@/api/endpoints";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import {
  campaignStatusLabel,
  campaignStatusVariant,
} from "@/lib/campaign-status";
import { timeAgo } from "@/lib/format";

import { CampaignCreateDialog } from "./CampaignCreateDialog";

export default function CampaignsList() {
  const { data: campaigns, isLoading, isError, error } = useQuery({
    queryKey: ["campaigns"],
    queryFn: () => endpoints.listCampaigns(),
  });

  return (
    <div>
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">Campaigns</h1>
          <p className="mt-2 text-black/60">
            Each campaign defines an ICP and runs the pipeline end-to-end.
          </p>
        </div>
        <CampaignCreateDialog />
      </div>

      <div className="mt-8 rounded-xl border border-black/10 bg-white overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-black/10 bg-black/[0.02]">
              <th className="text-left font-medium text-black/60 px-6 py-3">
                Name
              </th>
              <th className="text-left font-medium text-black/60 px-6 py-3">
                Status
              </th>
              <th className="text-left font-medium text-black/60 px-6 py-3">
                Industry
              </th>
              <th className="text-right font-medium text-black/60 px-6 py-3">
                Companies
              </th>
              <th className="text-right font-medium text-black/60 px-6 py-3">
                Drafts
              </th>
              <th className="text-right font-medium text-black/60 px-6 py-3">
                Created
              </th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <>
                {[0, 1, 2].map((i) => (
                  <tr key={i} className="border-b border-black/5">
                    {Array.from({ length: 6 }).map((_, j) => (
                      <td key={j} className="px-6 py-4">
                        <Skeleton className="h-4 w-24" />
                      </td>
                    ))}
                  </tr>
                ))}
              </>
            )}

            {isError && (
              <tr>
                <td
                  colSpan={6}
                  className="px-6 py-12 text-center text-red-600"
                >
                  Failed to load: {(error as Error).message}
                </td>
              </tr>
            )}

            {!isLoading && !isError && campaigns?.length === 0 && (
              <tr>
                <td colSpan={6} className="p-0">
                  <EmptyState
                    icon={<Megaphone className="size-5" />}
                    title="No campaigns yet"
                    description="Create a campaign to kick off the pipeline."
                  />
                </td>
              </tr>
            )}

            {campaigns?.map((c, i) => (
              <motion.tr
                key={c.id}
                className="border-b border-black/5 hover:bg-black/[0.02] transition-colors"
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: Math.min(i * 0.02, 0.4), duration: 0.25 }}
              >
                <td className="px-6 py-4">
                  <Link
                    to={`/app/campaigns/${c.id}`}
                    className="font-medium hover:underline"
                  >
                    {c.name}
                  </Link>
                  <div className="text-xs text-black/40 mt-0.5 font-mono">
                    {c.id}
                  </div>
                </td>
                <td className="px-6 py-4">
                  <Badge variant={campaignStatusVariant(c.status)}>
                    {campaignStatusLabel(c.status)}
                  </Badge>
                </td>
                <td className="px-6 py-4 text-black/70">{c.icp.industry}</td>
                <td className="px-6 py-4 text-right tabular-nums">
                  {c.counts?.companies ?? 0}
                </td>
                <td className="px-6 py-4 text-right tabular-nums">
                  {c.counts?.drafts ?? 0}
                </td>
                <td className="px-6 py-4 text-right text-black/50">
                  {timeAgo(c.created_at)}
                </td>
              </motion.tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
