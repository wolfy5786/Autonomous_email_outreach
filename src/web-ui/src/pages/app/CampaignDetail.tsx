import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { ArrowLeft, Building2, Mail, RefreshCw, Trash2 } from "lucide-react";

import { endpoints } from "@/api/endpoints";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import {
  campaignStatusLabel,
  campaignStatusVariant,
} from "@/lib/campaign-status";
import { formatDateTime } from "@/lib/format";

import { CampaignTimeline } from "@/components/app/CampaignTimeline";
import { PipelineStageStrip } from "@/components/app/PipelineStageStrip";

export default function CampaignDetail() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [confirmDelete, setConfirmDelete] = useState(false);

  const campaignQuery = useQuery({
    queryKey: ["campaign", id],
    queryFn: () => endpoints.getCampaign(id!),
    enabled: !!id,
  });

  const companiesQuery = useQuery({
    queryKey: ["campaign-companies", id],
    queryFn: () => endpoints.listCampaignCompanies(id!),
    enabled: !!id,
  });

  const draftsQuery = useQuery({
    queryKey: ["campaign-drafts", id],
    queryFn: () => endpoints.listCampaignDrafts(id!),
    enabled: !!id,
  });

  const prospectsQuery = useQuery({
    queryKey: ["campaign-prospects", id],
    queryFn: () => endpoints.listCampaignProspects(id!),
    enabled: !!id,
  });

  const rerun = useMutation({
    mutationFn: () => endpoints.rerunCampaign(id!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["campaign", id] });
      qc.invalidateQueries({ queryKey: ["campaigns"] });
    },
  });

  const purge = useMutation({
    mutationFn: () => endpoints.purgeCampaign(id!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["campaigns"] });
      navigate("/app/campaigns");
    },
  });

  if (campaignQuery.isLoading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-6 w-32" />
        <Skeleton className="h-10 w-2/3" />
        <Skeleton className="h-4 w-1/2" />
      </div>
    );
  }
  if (campaignQuery.isError || !campaignQuery.data) {
    return (
      <div className="text-center py-16">
        <p className="text-black/50">Campaign not found.</p>
        <Link
          to="/app/campaigns"
          className="mt-3 inline-block text-sm underline text-black/60"
        >
          ← back to campaigns
        </Link>
      </div>
    );
  }

  const c = campaignQuery.data;

  return (
    <div className="space-y-8">
      <div>
        <Link
          to="/app/campaigns"
          className="inline-flex items-center gap-2 text-sm text-black/60 hover:text-black"
        >
          <ArrowLeft className="size-4" />
          All campaigns
        </Link>
      </div>

      {/* Sticky campaign header — title, status, and pipeline progress stay
          visible while scrolling through tabs. */}
      <div className="sticky top-0 z-10 -mx-6 px-6 py-4 bg-neutral-50/95 backdrop-blur border-b border-black/5 space-y-4">
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div className="min-w-0">
            <h1 className="text-2xl font-semibold tracking-tight truncate">
              {c.name}
            </h1>
            <p className="mt-0.5 text-xs text-black/40 font-mono truncate">
              {c.id}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Badge variant={campaignStatusVariant(c.status)}>
              {campaignStatusLabel(c.status)}
            </Badge>
            {(c.status === "completed" || c.status === "failed") && (
              <div className="flex flex-col items-end gap-1">
                <Button
                  size="sm"
                  variant="outline"
                  disabled={rerun.isPending}
                  onClick={() => rerun.mutate()}
                >
                  <RefreshCw className="size-3.5 mr-1.5" />
                  {rerun.isPending ? "Rerunning…" : "Rerun"}
                </Button>
                {rerun.isError && (
                  <p className="text-xs text-red-600">
                    {(rerun.error as Error).message}
                  </p>
                )}
              </div>
            )}
            <div className="flex flex-col items-end gap-1">
              <Button
                size="sm"
                variant="destructive"
                disabled={purge.isPending}
                onClick={() => setConfirmDelete(true)}
              >
                <Trash2 className="size-3.5 mr-1.5" />
                Delete
              </Button>
              {purge.isError && (
                <p className="text-xs text-red-600">
                  {(purge.error as Error).message}
                </p>
              )}
            </div>
          </div>
        </div>
        <PipelineStageStrip status={c.status} />
      </div>

      {/* Quick stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Stat label="Companies" value={companiesQuery.data?.length ?? "—"} />
        <Stat label="Prospects" value={prospectsQuery.data?.count ?? "—"} />
        <Stat label="Drafts" value={draftsQuery.data?.length ?? "—"} />
        <Stat label="Created" value={formatDateTime(c.created_at)} mono />
      </div>

      {/* Tabs */}
      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="companies">
            Companies ({companiesQuery.data?.length ?? "·"})
          </TabsTrigger>
          <TabsTrigger value="drafts">
            Drafts ({draftsQuery.data?.length ?? "·"})
          </TabsTrigger>
          <TabsTrigger value="timeline">Timeline</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-6">
          <Section title="Ideal customer profile">
            <Kvp k="Industry" v={c.icp.industry} />
            <Kvp
              k="Employee range"
              v={`${c.icp.employee_range[0]}–${c.icp.employee_range[1]}`}
            />
            <Kvp
              k="Stack includes"
              v={c.icp.stack_includes.join(", ") || "—"}
            />
            <Kvp k="Geography" v={c.icp.geography.join(", ") || "—"} />
            <Kvp k="Pain" v={c.icp.pain} />
            {c.icp.additional_comment ? (
              <Kvp k="Additional notes" v={c.icp.additional_comment} />
            ) : null}
          </Section>
          <Section title="Product profile">
            <Kvp k="Name" v={c.product_profile.name} />
            <Kvp k="Value prop" v={c.product_profile.value_prop} />
            {c.product_profile.pricing && (
              <Kvp k="Pricing" v={c.product_profile.pricing} />
            )}
            {c.product_profile.differentiators && (
              <Kvp
                k="Differentiators"
                v={c.product_profile.differentiators.join(" · ")}
              />
            )}
          </Section>
        </TabsContent>

        <TabsContent value="companies">
          {companiesQuery.isLoading ? (
            <Skeleton className="h-32 w-full" />
          ) : (companiesQuery.data?.length ?? 0) === 0 ? (
            <div className="rounded-lg border border-black/10 bg-white">
              <EmptyState
                icon={<Building2 className="size-5" />}
                title="No companies sourced yet"
                description="The sourcing pipeline will populate this list once it discovers companies that match the ICP."
              />
            </div>
          ) : (
            <div className="rounded-lg border border-black/10 bg-white divide-y divide-black/5">
              {companiesQuery.data!.map((co, i) => (
                <motion.div
                  key={co.id}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: Math.min(i * 0.02, 0.4), duration: 0.25 }}
                >
                  <Link
                    to={`/app/companies/${co.id}`}
                    className="flex items-center gap-3 p-4 hover:bg-black/[0.02]"
                  >
                    <Avatar name={co.name} domain={co.domain ?? undefined} size={36} />
                    <div className="flex-1 min-w-0">
                      <div className="font-medium truncate">{co.name}</div>
                      <div className="text-xs text-black/40 truncate">
                        {co.domain ?? "—"} · {co.industry ?? "—"}
                      </div>
                    </div>
                    <div className="text-xs text-black/50 shrink-0">
                      {co.pocs.length} POC{co.pocs.length === 1 ? "" : "s"}
                    </div>
                  </Link>
                </motion.div>
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="drafts">
          {draftsQuery.isLoading ? (
            <Skeleton className="h-32 w-full" />
          ) : (draftsQuery.data?.length ?? 0) === 0 ? (
            <div className="rounded-lg border border-black/10 bg-white">
              <EmptyState
                icon={<Mail className="size-5" />}
                title="No drafts generated yet"
                description="As the pipeline reaches messaging, personalized drafts will appear here."
              />
            </div>
          ) : (
            <div className="rounded-lg border border-black/10 bg-white divide-y divide-black/5">
              {draftsQuery.data!.map((d, i) => (
                <motion.div
                  key={d.id}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: Math.min(i * 0.04, 0.4), duration: 0.25 }}
                >
                  <Link
                    to={`/app/drafts/${d.id}`}
                    className="block p-4 hover:bg-black/[0.02]"
                  >
                    <div className="flex items-center gap-2">
                      <Badge
                        variant={
                          d.status === "draft_created"
                            ? "success"
                            : d.status === "failed"
                              ? "destructive"
                              : "warning"
                        }
                      >
                        {d.status.replace("_", " ")}
                      </Badge>
                      <div className="font-medium truncate">{d.subject}</div>
                    </div>
                    <div className="text-xs text-black/50 mt-2 line-clamp-2">
                      {d.body}
                    </div>
                  </Link>
                </motion.div>
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="timeline">
          <CampaignTimeline campaignId={c.id} />
        </TabsContent>
      </Tabs>

      <Dialog open={confirmDelete} onOpenChange={setConfirmDelete}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete campaign?</DialogTitle>
            <DialogDescription>
              This will permanently delete <strong>{c.name}</strong> and all
              associated drafts. This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setConfirmDelete(false)}
              disabled={purge.isPending}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              disabled={purge.isPending}
              onClick={() => purge.mutate()}
            >
              {purge.isPending ? "Deleting…" : "Delete permanently"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function Stat({
  label,
  value,
  mono,
}: {
  label: string;
  value: string | number;
  mono?: boolean;
}) {
  return (
    <div className="rounded-lg border border-black/10 bg-white p-4">
      <div className="text-xs uppercase tracking-wide text-black/40">
        {label}
      </div>
      <div className={`mt-1 text-lg font-semibold ${mono ? "font-mono text-sm" : ""}`}>
        {value}
      </div>
    </div>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-lg border border-black/10 bg-white p-6">
      <h3 className="text-sm uppercase tracking-wide text-black/40">
        {title}
      </h3>
      <dl className="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-y-3 gap-x-6 text-sm">
        {children}
      </dl>
    </div>
  );
}

function Kvp({ k, v }: { k: string; v: string }) {
  return (
    <>
      <dt className="text-black/50">{k}</dt>
      <dd className="sm:col-span-2">{v}</dd>
    </>
  );
}
