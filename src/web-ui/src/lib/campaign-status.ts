import type { CampaignStatus } from "@/api/types";

const labels: Record<CampaignStatus, string> = {
  draft: "Draft",
  planning: "Planning",
  sourcing: "Sourcing",
  drafting: "Drafting",
  ready_for_review: "Ready for review",
  completed: "Completed",
  failed: "Failed",
};

const variants: Record<
  CampaignStatus,
  "outline" | "info" | "warning" | "success" | "destructive" | "secondary"
> = {
  draft: "outline",
  planning: "info",
  sourcing: "info",
  drafting: "warning",
  ready_for_review: "success",
  completed: "secondary",
  failed: "destructive",
};

export function campaignStatusLabel(s: CampaignStatus): string {
  return labels[s] ?? s;
}

export function campaignStatusVariant(s: CampaignStatus) {
  return variants[s] ?? "outline";
}
