import { motion } from "framer-motion";
import { Check, FileText, Map, Search, Send, Users } from "lucide-react";

import type { CampaignStatus } from "@/api/types";
import { cn } from "@/lib/utils";

type Stage = {
  key: CampaignStatus;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
};

const STAGES: Stage[] = [
  { key: "planning", label: "Planning", icon: Map },
  { key: "sourcing", label: "Sourcing", icon: Search },
  { key: "prospecting", label: "Prospecting", icon: Users },
  { key: "messaging", label: "Messaging", icon: FileText },
  { key: "completed", label: "Completed", icon: Send },
];

// Statuses that aren't part of the linear pipeline path but should still render
// the strip as fully done / cancelled. Keeps the UI honest.
const TERMINAL_OK: CampaignStatus[] = ["completed", "ready_for_review"];
const TERMINAL_BAD: CampaignStatus[] = ["failed", "cancelled"];
const PAUSED: CampaignStatus[] = ["paused"];

export function PipelineStageStrip({ status }: { status: CampaignStatus }) {
  const isTerminalOk = TERMINAL_OK.includes(status);
  const isTerminalBad = TERMINAL_BAD.includes(status);
  const isPaused = PAUSED.includes(status);
  const activeIdx = STAGES.findIndex((s) => s.key === status);
  // Cap to the last stage when terminal so all earlier steps show as done.
  const effectiveIdx = isTerminalOk
    ? STAGES.length - 1
    : isTerminalBad
      ? Math.max(activeIdx, 0)
      : activeIdx;

  return (
    <div className="w-full">
      <ol className="flex items-center gap-1">
        {STAGES.map((stage, i) => {
          const Icon = stage.icon;
          const done =
            (isTerminalOk && i < STAGES.length - 1) ||
            (effectiveIdx > -1 && i < effectiveIdx);
          const current = !isTerminalOk && i === effectiveIdx;
          const last = i === STAGES.length - 1;
          return (
            <li key={stage.key} className="flex-1 flex items-center min-w-0">
              <div className="flex flex-col items-center gap-2 min-w-0">
                <StepCircle
                  done={done}
                  current={current}
                  isFinal={last}
                  isError={isTerminalBad && current}
                  isPaused={isPaused && current}
                  Icon={Icon}
                />
                <span
                  className={cn(
                    "text-[11px] uppercase tracking-wide whitespace-nowrap",
                    current
                      ? "font-medium text-black"
                      : done
                        ? "text-black/60"
                        : "text-black/30",
                  )}
                >
                  {stage.label}
                </span>
              </div>
              {!last && (
                <div className="flex-1 h-px mx-1 relative">
                  <div className="absolute inset-0 bg-black/10" />
                  <motion.div
                    className="absolute inset-y-0 left-0 bg-emerald-500"
                    initial={{ width: 0 }}
                    animate={{ width: done ? "100%" : current ? "50%" : 0 }}
                    transition={{ duration: 0.6, ease: "easeOut" }}
                  />
                </div>
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function StepCircle({
  done,
  current,
  isFinal,
  isError,
  isPaused,
  Icon,
}: {
  done: boolean;
  current: boolean;
  isFinal: boolean;
  isError: boolean;
  isPaused: boolean;
  Icon: React.ComponentType<{ className?: string }>;
}) {
  const baseSize = "size-9";

  if (isError) {
    return (
      <div
        className={cn(
          baseSize,
          "rounded-full flex items-center justify-center border-2 border-red-500 bg-red-50 text-red-600",
        )}
      >
        <Icon className="size-4" />
      </div>
    );
  }

  if (done || (isFinal && current)) {
    return (
      <div
        className={cn(
          baseSize,
          "rounded-full flex items-center justify-center bg-emerald-500 text-white",
        )}
      >
        <Check className="size-4" />
      </div>
    );
  }

  if (current) {
    return (
      <div className="relative">
        {!isPaused && (
          <motion.div
            className="absolute inset-0 rounded-full bg-indigo-500/30"
            animate={{ scale: [1, 1.4, 1], opacity: [0.6, 0, 0.6] }}
            transition={{ duration: 1.8, repeat: Infinity }}
          />
        )}
        <div
          className={cn(
            baseSize,
            "relative rounded-full flex items-center justify-center text-white",
            isPaused ? "bg-amber-500" : "bg-indigo-500",
          )}
        >
          <Icon className="size-4" />
        </div>
      </div>
    );
  }

  return (
    <div
      className={cn(
        baseSize,
        "rounded-full flex items-center justify-center border border-black/15 bg-white text-black/30",
      )}
    >
      <Icon className="size-4" />
    </div>
  );
}
