import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Command } from "cmdk";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  Building2,
  LayoutDashboard,
  Mail,
  Megaphone,
  Search,
} from "lucide-react";

import { endpoints } from "@/api/endpoints";
import { campaignStatusLabel } from "@/lib/campaign-status";
import { cn } from "@/lib/utils";

/**
 * Search palette modal. Opened from a sidebar button. Lets the user jump to any
 * campaign by name/id, or to the top-level pages, without clicking through.
 */
export function CommandPalette({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (next: boolean) => void;
}) {
  const navigate = useNavigate();
  const [value, setValue] = useState("");

  const { data: campaigns } = useQuery({
    queryKey: ["campaigns"],
    queryFn: () => endpoints.listCampaigns(),
    enabled: open,
  });

  // Reset search when reopened.
  useEffect(() => {
    if (open) setValue("");
  }, [open]);

  function go(path: string) {
    onOpenChange(false);
    navigate(path);
  }

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 bg-black/30 backdrop-blur-sm flex items-start justify-center pt-[12vh] px-4"
      onClick={() => onOpenChange(false)}
    >
      <div
        className="w-full max-w-xl rounded-xl border border-black/10 bg-white shadow-xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <Command
          label="Global search"
          shouldFilter
          loop
          className="flex flex-col max-h-[60vh]"
        >
          <div className="flex items-center gap-2 px-4 border-b border-black/5">
            <Search className="size-4 text-black/40" />
            <Command.Input
              value={value}
              onValueChange={setValue}
              autoFocus
              placeholder="Search campaigns or jump to a page…"
              className="flex-1 py-3 outline-none text-sm placeholder:text-black/40"
            />
          </div>
          <Command.List className="flex-1 overflow-y-auto py-2">
            <Command.Empty className="px-4 py-8 text-sm text-center text-black/40">
              No matches.
            </Command.Empty>

            <Command.Group
              heading="Pages"
              className="[&_[cmdk-group-heading]]:px-4 [&_[cmdk-group-heading]]:py-1 [&_[cmdk-group-heading]]:text-[11px] [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-wide [&_[cmdk-group-heading]]:text-black/40"
            >
              <Row
                icon={<LayoutDashboard className="size-4" />}
                label="Overview"
                onSelect={() => go("/app")}
              />
              <Row
                icon={<Megaphone className="size-4" />}
                label="Campaigns"
                onSelect={() => go("/app/campaigns")}
              />
              <Row
                icon={<Building2 className="size-4" />}
                label="Companies"
                onSelect={() => go("/app/companies")}
              />
              <Row
                icon={<Mail className="size-4" />}
                label="Drafts"
                onSelect={() => go("/app/drafts")}
              />
              <Row
                icon={<Activity className="size-4" />}
                label="Observability"
                onSelect={() => go("/app/observability")}
              />
            </Command.Group>

            {campaigns && campaigns.length > 0 && (
              <Command.Group
                heading="Campaigns"
                className="[&_[cmdk-group-heading]]:px-4 [&_[cmdk-group-heading]]:py-1 [&_[cmdk-group-heading]]:text-[11px] [&_[cmdk-group-heading]]:uppercase [&_[cmdk-group-heading]]:tracking-wide [&_[cmdk-group-heading]]:text-black/40"
              >
                {campaigns.slice(0, 50).map((c) => (
                  <Row
                    key={c.id}
                    icon={<Megaphone className="size-4" />}
                    label={c.name}
                    sub={`${campaignStatusLabel(c.status)} · ${c.id.slice(0, 8)}`}
                    onSelect={() => go(`/app/campaigns/${c.id}`)}
                    value={`${c.name} ${c.id}`}
                  />
                ))}
              </Command.Group>
            )}
          </Command.List>
        </Command>
      </div>
    </div>
  );
}

function Row({
  icon,
  label,
  sub,
  onSelect,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  sub?: string;
  onSelect: () => void;
  value?: string;
}) {
  return (
    <Command.Item
      value={value ?? label}
      onSelect={onSelect}
      className={cn(
        "flex items-center gap-3 px-4 py-2 cursor-pointer text-sm",
        "aria-selected:bg-black/[0.05]",
      )}
    >
      <span className="text-black/50">{icon}</span>
      <span className="flex-1 min-w-0 truncate">{label}</span>
      {sub && (
        <span className="text-xs text-black/40 truncate max-w-[40%]">
          {sub}
        </span>
      )}
    </Command.Item>
  );
}
