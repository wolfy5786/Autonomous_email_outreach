import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Building2, ExternalLink, Mail } from "lucide-react";

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
      </div>

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
    </div>
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
