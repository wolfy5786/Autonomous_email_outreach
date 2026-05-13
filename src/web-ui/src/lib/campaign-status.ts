import type { CampaignStatus } from "@/api/types";

const labels: Record<CampaignStatus, string> = {
  pending: "Pending",
  draft: "Draft",
  planning: "Planning",
  sourcing: "Sourcing",
  prospecting: "Prospecting",
  drafting: "Drafting",
  messaging: "Messaging",
  paused: "Paused",
  ready_for_review: "Ready for review",
  completed: "Completed",
  failed: "Failed",
  cancelled: "Cancelled",
};

const variants: Record<
  CampaignStatus,
  "outline" | "info" | "warning" | "success" | "destructive" | "secondary"
> = {
  pending: "outline",
  draft: "outline",
  planning: "info",
  sourcing: "info",
  prospecting: "info",
  drafting: "warning",
  messaging: "warning",
  paused: "secondary",
  ready_for_review: "success",
  completed: "secondary",
  failed: "destructive",
  cancelled: "secondary",
};

export function campaignStatusLabel(s: CampaignStatus): string {
  return labels[s] ?? s;
}

export function campaignStatusVariant(s: CampaignStatus) {
  return variants[s] ?? "outline";
}
