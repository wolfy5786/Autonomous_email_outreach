/**
 * All companies across every campaign, in one table. Filterable by campaign
 * via the campaign-id query param (?campaign=c-acme-001).
 */

import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQueries, useQuery } from "@tanstack/react-query";
import { Building2, Search } from "lucide-react";

import { endpoints } from "@/api/endpoints";
import type { CompanyDetail } from "@/api/types";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";

type RowWithCampaign = CompanyDetail & { campaign_id: string };

export default function CompaniesList() {
  const [params, setParams] = useSearchParams();
  const campaignFilter = params.get("campaign") ?? "";
  const [search, setSearch] = useState("");

  const campaignsQuery = useQuery({
    queryKey: ["campaigns"],
    queryFn: () => endpoints.listCampaigns(),
  });

  const companyQueries = useQueries({
    queries: (campaignsQuery.data ?? []).map((c) => ({
      queryKey: ["campaign-companies", c.id],
      queryFn: () => endpoints.listCampaignCompanies(c.id),
      enabled: !!campaignsQuery.data,
    })),
  });

  const allRows: RowWithCampaign[] = useMemo(() => {
    if (!campaignsQuery.data) return [];
    return campaignsQuery.data.flatMap((c, i) =>
      (companyQueries[i]?.data ?? []).map((co) => ({
        ...co,
        campaign_id: c.id,
      })),
    );
  }, [campaignsQuery.data, companyQueries]);

  const rows = useMemo(() => {
    return allRows.filter((co) => {
      if (campaignFilter && co.campaign_id !== campaignFilter) return false;
      if (!search) return true;
      const q = search.toLowerCase();
      return (
        co.name.toLowerCase().includes(q) ||
        co.domain?.toLowerCase().includes(q) ||
        co.industry?.toLowerCase().includes(q)
      );
    });
  }, [allRows, campaignFilter, search]);

  const isLoading =
    campaignsQuery.isLoading || companyQueries.some((q) => q.isLoading);

  return (
    <div>
      <div>
        <h1 className="text-3xl font-semibold tracking-tight">Companies</h1>
        <p className="mt-2 text-black/60">
          Every company discovered by the sourcing pipeline, across all
          campaigns.
        </p>
      </div>

      <div className="mt-6 flex items-center gap-3 flex-wrap">
        <div className="relative flex-1 min-w-[240px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-black/40" />
          <Input
            placeholder="Search by name, domain, or industry"
            className="pl-9"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <select
          value={campaignFilter}
          onChange={(e) => {
            const v = e.target.value;
            if (v) setParams({ campaign: v });
            else setParams({});
          }}
          className="h-10 rounded-md border border-black/10 bg-white px-3 text-sm"
        >
          <option value="">All campaigns</option>
          {campaignsQuery.data?.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
      </div>

      <div className="mt-6 rounded-xl border border-black/10 bg-white overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-black/10 bg-black/[0.02]">
              <th className="text-left font-medium text-black/60 px-6 py-3">
                Name
              </th>
              <th className="text-left font-medium text-black/60 px-6 py-3">
                Industry
              </th>
              <th className="text-left font-medium text-black/60 px-6 py-3">
                HQ
              </th>
              <th className="text-right font-medium text-black/60 px-6 py-3">
                Employees
              </th>
              <th className="text-right font-medium text-black/60 px-6 py-3">
                POCs
              </th>
            </tr>
          </thead>
          <tbody>
            {isLoading && (
              <>
                {[0, 1, 2].map((i) => (
                  <tr key={i} className="border-b border-black/5">
                    {Array.from({ length: 5 }).map((_, j) => (
                      <td key={j} className="px-6 py-4">
                        <Skeleton className="h-4 w-24" />
                      </td>
                    ))}
                  </tr>
                ))}
              </>
            )}

            {!isLoading && rows.length === 0 && (
              <tr>
                <td
                  colSpan={5}
                  className="px-6 py-16 text-center text-black/50"
                >
                  <Building2 className="mx-auto size-8 text-black/20" />
                  <div className="mt-3">No companies matched.</div>
                </td>
              </tr>
            )}

            {rows.map((co) => (
              <tr
                key={co.id}
                className="border-b border-black/5 hover:bg-black/[0.02]"
              >
                <td className="px-6 py-4">
                  <Link
                    to={`/app/companies/${co.id}`}
                    className="font-medium hover:underline"
                  >
                    {co.name}
                  </Link>
                  <div className="text-xs text-black/40">
                    {co.domain ?? "—"}
                  </div>
                </td>
                <td className="px-6 py-4 text-black/70">
                  {co.industry ?? "—"}
                </td>
                <td className="px-6 py-4 text-black/70">
                  {co.hq
                    ? [co.hq.city, co.hq.region, co.hq.country]
                        .filter(Boolean)
                        .join(", ")
                    : "—"}
                </td>
                <td className="px-6 py-4 text-right tabular-nums">
                  {co.employee_count ?? "—"}
                </td>
                <td className="px-6 py-4 text-right tabular-nums">
                  {co.pocs.length}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
