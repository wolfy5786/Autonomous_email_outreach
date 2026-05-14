import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  Building2,
  ExternalLink,
  Linkedin,
  Mail,
} from "lucide-react";

import { endpoints } from "@/api/endpoints";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";

export default function CompanyDetail() {
  const { id } = useParams<{ id: string }>();

  const { data: company, isLoading, isError } = useQuery({
    queryKey: ["company", id],
    queryFn: () => endpoints.getCompany(id!),
    enabled: !!id,
  });

  if (isLoading) {
    return <Skeleton className="h-32 w-full" />;
  }
  if (isError || !company) {
    return (
      <div className="text-center py-16">
        <p className="text-black/50">Company not found.</p>
        <Link
          to="/app/companies"
          className="mt-3 inline-block text-sm underline text-black/60"
        >
          ← back to companies
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div>
        <Link
          to="/app/companies"
          className="inline-flex items-center gap-2 text-sm text-black/60 hover:text-black"
        >
          <ArrowLeft className="size-4" />
          All companies
        </Link>
        <div className="mt-3 flex items-start gap-4">
          <div className="size-12 rounded-md bg-black text-white flex items-center justify-center">
            <Building2 className="size-6" />
          </div>
          <div>
            <h1 className="text-3xl font-semibold tracking-tight">
              {company.name}
            </h1>
            {company.domain && (
              <a
                href={`https://${company.domain}`}
                target="_blank"
                rel="noreferrer"
                className="mt-1 inline-flex items-center gap-1 text-sm text-black/60 hover:text-black"
              >
                {company.domain}
                <ExternalLink className="size-3" />
              </a>
            )}
          </div>
        </div>
      </div>

      {/* Quick facts */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Fact label="Industry" value={company.industry ?? "—"} />
        <Fact
          label="Employees"
          value={company.employee_count?.toLocaleString() ?? "—"}
        />
        <Fact
          label="HQ"
          value={
            company.hq
              ? [company.hq.city, company.hq.region, company.hq.country]
                  .filter(Boolean)
                  .join(", ")
              : "—"
          }
        />
        <Fact
          label="Last scrape"
          value={company.last_scrape_mode ?? "—"}
          variant={
            company.last_scrape_mode === "all"
              ? "success"
              : company.last_scrape_mode === "partial"
                ? "warning"
                : undefined
          }
        />
        <Fact
          label="Funding stage"
          value={company.funding_stage ?? "—"}
        />
        <Fact
          label="ICP fit score"
          value={formatScore(company.icp_fit_score)}
        />
        <Fact
          label="Data completeness"
          value={formatPercent(company.data_completeness)}
        />
        <Fact
          label="Enriched"
          value={
            company.enriched === undefined
              ? "—"
              : company.enriched
                ? "yes"
                : "no"
          }
          variant={company.enriched ? "success" : undefined}
        />
      </div>

      {/* Description */}
      {company.description && (
        <div>
          <h2 className="text-sm uppercase tracking-wide text-black/40 mb-2">
            Description
          </h2>
          <p className="text-sm leading-relaxed text-black/80 whitespace-pre-line">
            {company.description}
          </p>
        </div>
      )}

      {/* Tech stack */}
      {company.tech_stack && company.tech_stack.length > 0 && (
        <div>
          <h2 className="text-sm uppercase tracking-wide text-black/40 mb-3">
            Tech stack
          </h2>
          <div className="flex flex-wrap gap-2">
            {company.tech_stack.map((tech) => (
              <Badge key={tech} variant="outline">
                {tech}
              </Badge>
            ))}
          </div>
        </div>
      )}

      {/* Links + freshness */}
      {(company.linkedin_url ||
        company.website_url ||
        company.freshness_timestamp) && (
        <div>
          <h2 className="text-sm uppercase tracking-wide text-black/40 mb-3">
            Links
          </h2>
          <div className="flex flex-wrap items-center gap-4 text-sm">
            {company.website_url && (
              <a
                href={company.website_url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 text-black/70 hover:text-black"
              >
                <ExternalLink className="size-3" />
                Website
              </a>
            )}
            {company.linkedin_url && (
              <a
                href={company.linkedin_url}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 text-black/70 hover:text-black"
              >
                <Linkedin className="size-3" />
                LinkedIn
              </a>
            )}
            {company.freshness_timestamp && (
              <span className="text-black/50">
                Last refreshed{" "}
                {new Date(company.freshness_timestamp).toLocaleString()}
              </span>
            )}
          </div>
        </div>
      )}

      {/* Campaigns */}
      {company.campaign_ids && company.campaign_ids.length > 0 && (
        <div>
          <h2 className="text-sm uppercase tracking-wide text-black/40 mb-3">
            Campaigns ({company.campaign_ids.length})
          </h2>
          <div className="flex flex-wrap gap-2">
            {company.campaign_ids.map((cid) => (
              <Link
                key={cid}
                to={`/app/campaigns/${cid}`}
                className="inline-flex items-center"
              >
                <Badge variant="outline" className="hover:bg-black/5">
                  {cid}
                </Badge>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* POCs */}
      <div>
        <h2 className="text-sm uppercase tracking-wide text-black/40 mb-3">
          Persons of contact ({company.pocs.length})
        </h2>
        {company.pocs.length === 0 ? (
          <div className="rounded-lg border border-dashed border-black/15 p-8 text-center text-sm text-black/40">
            No POCs identified yet.
          </div>
        ) : (
          <div className="rounded-lg border border-black/10 bg-white divide-y divide-black/5">
            {company.pocs.map((p) => (
              <div
                key={p.id}
                className="flex items-start gap-4 p-4"
              >
                <div className="size-10 rounded-full bg-neutral-100 flex items-center justify-center font-medium text-sm">
                  {p.full_name
                    .split(" ")
                    .map((n) => n[0])
                    .join("")
                    .slice(0, 2)
                    .toUpperCase()}
                </div>
                <div className="flex-1">
                  <div className="font-medium">{p.full_name}</div>
                  <div className="text-sm text-black/60">{p.title ?? ""}</div>
                  <div className="mt-2 flex items-center gap-4 text-xs text-black/50">
                    {p.email && (
                      <a
                        href={`mailto:${p.email}`}
                        className="inline-flex items-center gap-1 hover:text-black"
                      >
                        <Mail className="size-3" />
                        {p.email}
                      </a>
                    )}
                    {p.linkedin_url && (
                      <a
                        href={p.linkedin_url}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-flex items-center gap-1 hover:text-black"
                      >
                        <ExternalLink className="size-3" />
                        LinkedIn
                      </a>
                    )}
                    {p.seniority && (
                      <Badge variant="outline">{p.seniority}</Badge>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Raw fields — free-form Mongo dicts kept as collapsible JSON */}
      {(hasEntries(company.provenance) || hasEntries(company.extra)) && (
        <div>
          <h2 className="text-sm uppercase tracking-wide text-black/40 mb-3">
            Raw fields
          </h2>
          <div className="space-y-3">
            {hasEntries(company.provenance) && (
              <RawJsonBlock
                label="provenance"
                value={company.provenance as Record<string, unknown>}
              />
            )}
            {hasEntries(company.extra) && (
              <RawJsonBlock
                label="extra"
                value={company.extra as Record<string, unknown>}
              />
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function formatScore(v: number | undefined): string {
  if (typeof v !== "number" || Number.isNaN(v)) return "—";
  return v.toFixed(2);
}

function formatPercent(v: number | undefined): string {
  if (typeof v !== "number" || Number.isNaN(v)) return "—";
  return `${Math.round(v * 100)}%`;
}

function hasEntries(v: unknown): boolean {
  return (
    typeof v === "object" &&
    v !== null &&
    !Array.isArray(v) &&
    Object.keys(v).length > 0
  );
}

function RawJsonBlock({
  label,
  value,
}: {
  label: string;
  value: Record<string, unknown>;
}) {
  return (
    <details className="rounded-lg border border-black/10 bg-white">
      <summary className="cursor-pointer px-4 py-3 text-sm font-medium text-black/70 hover:bg-black/[0.02]">
        {label}{" "}
        <span className="text-black/40 font-normal">
          ({Object.keys(value).length}{" "}
          {Object.keys(value).length === 1 ? "key" : "keys"})
        </span>
      </summary>
      <pre className="px-4 pb-4 overflow-x-auto text-xs leading-relaxed text-black/70">
        {JSON.stringify(value, null, 2)}
      </pre>
    </details>
  );
}

function Fact({
  label,
  value,
  variant,
}: {
  label: string;
  value: string;
  variant?: "success" | "warning";
}) {
  return (
    <div className="rounded-lg border border-black/10 bg-white p-4">
      <div className="text-xs uppercase tracking-wide text-black/40">
        {label}
      </div>
      <div className="mt-1 font-medium">
        {variant ? (
          <Badge variant={variant}>{value}</Badge>
        ) : (
          value
        )}
      </div>
    </div>
  );
}
