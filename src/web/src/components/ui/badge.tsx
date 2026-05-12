import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";

import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium transition-colors",
  {
    variants: {
      variant: {
        default: "border-transparent bg-black text-white",
        secondary: "border-transparent bg-neutral-100 text-neutral-700",
        outline: "border-black/10 text-black/70",
        success:
          "border-emerald-300 bg-emerald-50 text-emerald-700",
        warning:
          "border-amber-300 bg-amber-50 text-amber-700",
        info: "border-indigo-300 bg-indigo-50 text-indigo-700",
        destructive:
          "border-red-300 bg-red-50 text-red-700",
      },
    },
    defaultVariants: { variant: "default" },
  },
);

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <span className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}
