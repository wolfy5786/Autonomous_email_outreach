import { useState } from "react";

import { cn } from "@/lib/utils";

/**
 * Square-rounded avatar that tries Clearbit's free logo API for a domain and
 * falls back to colourful initials. Stable colour per name so the same person
 * always gets the same hue.
 */
export function Avatar({
  name,
  domain,
  size = 40,
  className,
}: {
  name?: string | null;
  domain?: string | null;
  size?: number;
  className?: string;
}) {
  const [imgFailed, setImgFailed] = useState(false);
  const initials = computeInitials(name);
  const bg = colourFor(name ?? domain ?? "?");
  const logoUrl = domain ? `https://logo.clearbit.com/${domain}` : null;
  const showImg = logoUrl && !imgFailed;

  return (
    <div
      className={cn(
        "shrink-0 inline-flex items-center justify-center rounded-md font-medium text-white overflow-hidden",
        className,
      )}
      style={{
        width: size,
        height: size,
        background: bg,
        fontSize: Math.floor(size * 0.4),
      }}
      aria-label={name ?? domain ?? "avatar"}
    >
      {showImg ? (
        <img
          src={logoUrl}
          alt={name ?? domain ?? ""}
          width={size}
          height={size}
          className="object-cover w-full h-full"
          onError={() => setImgFailed(true)}
          loading="lazy"
        />
      ) : (
        <span>{initials || "?"}</span>
      )}
    </div>
  );
}

function computeInitials(name?: string | null): string {
  if (!name) return "";
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

// Deterministic hash → HSL pastel-ish background. Same name always same colour.
function colourFor(seed: string): string {
  let h = 0;
  for (let i = 0; i < seed.length; i += 1) {
    h = (h * 31 + seed.charCodeAt(i)) >>> 0;
  }
  const hue = h % 360;
  return `linear-gradient(135deg, hsl(${hue} 65% 55%), hsl(${(hue + 40) % 360} 55% 45%))`;
}
