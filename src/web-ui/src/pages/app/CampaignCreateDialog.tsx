import { FormEvent, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { endpoints } from "@/api/endpoints";
import { buildOrchestratorCreatePayload } from "@/api/normalize";
import type { ICP, ProductProfile } from "@/api/types";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

type FormState = {
  name: string;
  campaign_goal: string;
  icp: ICP;
  product_profile: ProductProfile;
};

const DEFAULT: FormState = {
  name: "",
  campaign_goal: "",
  icp: {
    industry: "",
    employee_range: [50, 500],
    stack_includes: [],
    geography: ["US"],
    pain: "",
    additional_comment: "",
  },
  product_profile: {
    name: "",
    value_prop: "",
    differentiators: [],
  },
};

export function CampaignCreateDialog() {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<FormState>(DEFAULT);
  const [stackInput, setStackInput] = useState("");
  const [rangeError, setRangeError] = useState<string | null>(null);

  const qc = useQueryClient();

  const create = useMutation({
    mutationFn: (vars: { body: FormState; stack: string[] }) =>
      endpoints.createCampaign(
        buildOrchestratorCreatePayload(
          vars.body.name,
          { ...vars.body.icp, campaign_goal: vars.body.campaign_goal || undefined },
          vars.body.product_profile,
          vars.stack,
        ),
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["campaigns"] });
      setOpen(false);
      setForm(DEFAULT);
      setStackInput("");
      setRangeError(null);
    },
  });

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const stack = stackInput
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    const [minE, maxE] = form.icp.employee_range;
    if (maxE < minE) {
      setRangeError("Maximum headcount must be greater than or equal to minimum.");
      return;
    }
    setRangeError(null);
    create.mutate({ body: form, stack });
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>New campaign</Button>
      </DialogTrigger>
      <DialogContent className="flex flex-col max-h-[90vh]">
        <DialogHeader>
          <DialogTitle>New campaign</DialogTitle>
          <DialogDescription>
            Describe your ideal customer and product. We use this to find
            prospects and write drafts.
          </DialogDescription>
        </DialogHeader>

        <form id="campaign-form" onSubmit={handleSubmit} className="grid gap-4 overflow-y-auto pr-1">
          <div className="grid gap-2">
            <Label htmlFor="name">Campaign name</Label>
            <Input
              id="name"
              required
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="Q3 enterprise platform launch"
            />
          </div>

          <div className="grid gap-2">
            <Label htmlFor="campaign-goal">
              Campaign goal{" "}
              <span className="font-normal text-black/50">(optional)</span>
            </Label>
            <Input
              id="campaign-goal"
              value={form.campaign_goal}
              onChange={(e) => setForm({ ...form, campaign_goal: e.target.value })}
              placeholder="Book a discovery call with the VP of Engineering"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-2">
              <Label htmlFor="emp-min">ICP — employees (min)</Label>
              <Input
                id="emp-min"
                type="number"
                required
                min={0}
                value={form.icp.employee_range[0]}
                onChange={(e) => {
                  const v = Number.parseInt(e.target.value, 10);
                  const n = Number.isFinite(v) ? Math.max(0, v) : 0;
                  setForm({
                    ...form,
                    icp: {
                      ...form.icp,
                      employee_range: [n, form.icp.employee_range[1]],
                    },
                  });
                }}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="emp-max">ICP — employees (max)</Label>
              <Input
                id="emp-max"
                type="number"
                required
                min={0}
                value={form.icp.employee_range[1]}
                onChange={(e) => {
                  const v = Number.parseInt(e.target.value, 10);
                  const n = Number.isFinite(v) ? Math.max(0, v) : 0;
                  setForm({
                    ...form,
                    icp: {
                      ...form.icp,
                      employee_range: [form.icp.employee_range[0], n],
                    },
                  });
                }}
              />
            </div>
          </div>

          {rangeError ? (
            <div className="text-sm text-red-600">{rangeError}</div>
          ) : null}

          <div className="grid grid-cols-2 gap-3">
            <div className="grid gap-2">
              <Label htmlFor="industry">ICP — industry</Label>
              <Input
                id="industry"
                required
                value={form.icp.industry}
                onChange={(e) =>
                  setForm({
                    ...form,
                    icp: { ...form.icp, industry: e.target.value },
                  })
                }
                placeholder="B2B SaaS"
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="stack">ICP — stack (comma-separated)</Label>
              <Input
                id="stack"
                value={stackInput}
                onChange={(e) => setStackInput(e.target.value)}
                placeholder="Kubernetes, AWS"
              />
            </div>
          </div>

          <div className="grid gap-2">
            <Label htmlFor="pain">ICP — pain you solve</Label>
            <Textarea
              id="pain"
              required
              value={form.icp.pain}
              onChange={(e) =>
                setForm({
                  ...form,
                  icp: { ...form.icp, pain: e.target.value },
                })
              }
              placeholder="Slow incident response, hard-to-trace deploys"
            />
          </div>

          <div className="grid gap-2">
            <Label htmlFor="additional-comment">
              ICP — additional notes{" "}
              <span className="font-normal text-black/50">(optional)</span>
            </Label>
            <Textarea
              id="additional-comment"
              value={form.icp.additional_comment ?? ""}
              onChange={(e) =>
                setForm({
                  ...form,
                  icp: {
                    ...form.icp,
                    additional_comment: e.target.value,
                  },
                })
              }
              placeholder="Exclusions, must-have signals, tone constraints…"
            />
          </div>

          <div className="grid gap-2">
            <Label htmlFor="product-name">Product name</Label>
            <Input
              id="product-name"
              required
              value={form.product_profile.name}
              onChange={(e) =>
                setForm({
                  ...form,
                  product_profile: {
                    ...form.product_profile,
                    name: e.target.value,
                  },
                })
              }
              placeholder="Acme Observability"
            />
          </div>

          <div className="grid gap-2">
            <Label htmlFor="value">Product — value prop</Label>
            <Textarea
              id="value"
              required
              value={form.product_profile.value_prop}
              onChange={(e) =>
                setForm({
                  ...form,
                  product_profile: {
                    ...form.product_profile,
                    value_prop: e.target.value,
                  },
                })
              }
              placeholder="Correlate deploys with runtime anomalies in under two minutes."
            />
          </div>

          {create.isError && (
            <div className="text-sm text-red-600">
              {(create.error as Error).message}
            </div>
          )}
        </form>

        <DialogFooter className="pt-2 border-t shrink-0">
          <Button
            type="button"
            variant="outline"
            onClick={() => setOpen(false)}
          >
            Cancel
          </Button>
          <Button type="submit" form="campaign-form" disabled={create.isPending}>
            {create.isPending ? "Creating…" : "Create campaign"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
