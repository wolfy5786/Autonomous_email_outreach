import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/** Empty-state slot used across list pages — icon + title + helpful text + optional action. */
export function EmptyState({
  icon,
  title,
  description,
  action,
  className,
}: {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center text-center py-16 px-6",
        className,
      )}
    >
      {icon && (
        <div className="size-12 rounded-full bg-black/[0.04] flex items-center justify-center text-black/40">
          {icon}
        </div>
      )}
      <h3 className="mt-4 text-base font-medium text-black/80">{title}</h3>
      {description && (
        <p className="mt-1 text-sm text-black/50 max-w-sm">{description}</p>
      )}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}
