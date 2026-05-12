import { FormEvent, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { endpoints } from "@/api/endpoints";
import type { CampaignCreateRequest } from "@/api/types";
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

const DEFAULT: CampaignCreateRequest = {
  name: "",
  icp: {
    industry: "",
    employee_range: [50, 500],
    stack_includes: [],
    geography: ["US"],
    pain: "",
  },
  product_profile: {
    name: "",
    value_prop: "",
    differentiators: [],
  },
};

export function CampaignCreateDialog() {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<CampaignCreateRequest>(DEFAULT);
  const [stackInput, setStackInput] = useState("");

  const qc = useQueryClient();

  const create = useMutation({
    mutationFn: () => endpoints.createCampaign(form),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["campaigns"] });
      setOpen(false);
      setForm(DEFAULT);
      setStackInput("");
    },
  });

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const stack = stackInput
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    setForm((f) => ({ ...f, icp: { ...f.icp, stack_includes: stack } }));
    create.mutate();
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>New campaign</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New campaign</DialogTitle>
          <DialogDescription>
            Describe your ideal customer and product. We use this to find
            prospects and write drafts.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="grid gap-4">
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

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setOpen(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={create.isPending}>
              {create.isPending ? "Creating…" : "Create campaign"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
