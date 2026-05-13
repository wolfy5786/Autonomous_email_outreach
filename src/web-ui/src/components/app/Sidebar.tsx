import { useState } from "react";
import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Megaphone,
  Building2,
  Mail,
  Activity,
  Search,
} from "lucide-react";

import { cn } from "@/lib/utils";

import { CommandPalette } from "./CommandPalette";

const items = [
  { to: "/app", label: "Overview", icon: LayoutDashboard, end: true },
  { to: "/app/campaigns", label: "Campaigns", icon: Megaphone },
  { to: "/app/companies", label: "Companies", icon: Building2 },
  { to: "/app/drafts", label: "Drafts", icon: Mail },
  { to: "/app/observability", label: "Observability", icon: Activity },
];

export function Sidebar() {
  const [paletteOpen, setPaletteOpen] = useState(false);

  return (
    <>
      <aside className="hidden md:flex flex-col w-60 shrink-0 border-r border-black/10 bg-white">
        <a
          href="/"
          className="h-16 flex items-center px-6 border-b border-black/10 font-semibold tracking-tight"
        >
          Outreach<span className="text-black/40">.</span>
        </a>

        {/* Quick-find launcher */}
        <div className="px-3 pt-3">
          <button
            type="button"
            onClick={() => setPaletteOpen(true)}
            className="w-full flex items-center gap-2 rounded-md border border-black/10 bg-black/[0.02] hover:bg-black/[0.04] px-3 py-2 text-sm text-black/50 transition-colors"
          >
            <Search className="size-4" />
            <span>Quick find…</span>
          </button>
        </div>

        <nav className="flex-1 px-3 py-3 space-y-1">
          {items.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors",
                  isActive
                    ? "bg-black text-white"
                    : "text-black/70 hover:bg-black/5 hover:text-black",
                )
              }
            >
              <item.icon className="size-4" />
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} />
    </>
  );
}
