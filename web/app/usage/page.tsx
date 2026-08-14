import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { RangeMenu } from "@/components/RangeMenu";
import { RouterSavingsChart } from "@/components/RouterSavingsChart";
import { StatCard } from "@/components/StatCard";
import { UsageChart } from "@/components/UsageChart";
import { getHealth, getOrgUsage, getOverview } from "@/lib/api";
import { compact, parseRange, pct, RANGE_LABEL, shortTs, usd } from "@/lib/format";
import type { Range } from "@/lib/types";

export default async function UsagePage({
  searchParams,
}: {
  searchParams: Promise<{ range?: string }>;
}) {
  const range = parseRange((await searchParams).range);
  const [overviewRes, healthRes, orgRes] = await Promise.all([
    getOverview(range),
    getHealth(),
    getOrgUsage(range),
  ]);
  const o = overviewRes.data!;
  const h = healthRes.data!;
  const org = orgRes.data?.overview;
  const errors = orgRes.data?.errors ?? [];
  const hrefs = Object.fromEntries(
    (Object.keys(RANGE_LABEL) as Range[]).map((r) => [r, `/usage?range=${r}`]),
  ) as Record<Range, string>;

  return (
    <div className="mx-auto max-w-[1360px] px-11 pt-[26px] pb-[120px]">
      <div className="mb-[18px] flex items-end justify-between">
        <div>
          <h2 className="text-xl font-semibold">Usage</h2>
          <p className="mt-1 text-[13px] text-muted-foreground">
            Local router hops vs AIand org analytics. These layers are not the same traffic.
          </p>
        </div>
        <RangeMenu range={range} hrefs={hrefs} />
      </div>

      {overviewRes.error && !overviewRes.ok ? (
        <Alert className="mb-4">
          <AlertTitle>Console overview unavailable</AlertTitle>
          <AlertDescription>{overviewRes.error}. Empty zeros below.</AlertDescription>
        </Alert>
      ) : null}

      <div className="mt-3 mb-[18px]">
        <h2 className="text-base font-semibold">This router</h2>
      </div>
      <div className="grid gap-[18px] sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Routed requests" value={String(o.routed_requests)} />
        <StatCard
          label="Spend"
          value={usd(h.spend_usd || o.spend_usd)}
          sub={`budget ${usd(h.budget_usd || o.budget_usd)}`}
        />
        <StatCard label="Savings" value={usd(o.savings_usd)} sub={pct(o.savings_pct)} green />
        <StatCard label="Cache hits" value={String(o.cache_hits)} />
      </div>

      <div className="mt-[42px] mb-[18px]">
        <h2 className="text-base font-semibold">AIand org</h2>
        <p className="mt-1 text-[13px] text-muted-foreground">
          Direct traffic that did not use this router. Not-saved is actual spend versus Flash.
        </p>
      </div>

      {!orgRes.ok || !org ? (
        <Alert className="mb-4">
          <AlertTitle>AIand org usage unavailable</AlertTitle>
          <AlertDescription>{orgRes.error}. Set DATA_AIAND_API_KEY in web/.env.local.</AlertDescription>
        </Alert>
      ) : (
        <>
          <div className="grid gap-[18px] sm:grid-cols-2 lg:grid-cols-4">
            <StatCard
              label="Org requests"
              value={String(org.routed_requests)}
              sub={`${compact(org.org_input_tokens)} in · ${compact(org.org_output_tokens)} out`}
            />
            <StatCard label="Your spend" value={usd(org.spend_usd)} sub="est. from recent mix" />
            <StatCard
              label="Could save"
              value={usd(org.unsaved_usd)}
              sub={`${usd(org.cost_routed_usd)} with router · est.`}
            />
            <StatCard
              label="Not saved"
              value={usd(org.unsaved_usd)}
              sub="router was not used"
            />
          </div>

          <div className="mt-[18px] grid gap-[18px] lg:grid-cols-2">
            <Card className="gap-0 py-0">
              <CardHeader className="pt-[22px]">
                <CardTitle className="text-[15px]">Requests</CardTitle>
                <CardDescription>GET /analytics/metrics · {RANGE_LABEL[range]}</CardDescription>
              </CardHeader>
              <CardContent className="pb-[22px]">
                {org.usage_buckets.length === 0 ? (
                  <Empty className="mt-[18px] min-h-[150px] border border-dashed">
                    <EmptyHeader>
                      <EmptyTitle>No metrics series</EmptyTitle>
                      <EmptyDescription>The upstream metrics payload was empty.</EmptyDescription>
                    </EmptyHeader>
                  </Empty>
                ) : (
                  <UsageChart buckets={org.usage_buckets} candidates={org.candidates} />
                )}
              </CardContent>
            </Card>
            <RouterSavingsChart buckets={org.usage_buckets} unrealized />
          </div>

          <Card className="mt-[18px] gap-0 py-0">
            <CardHeader className="pt-[22px]">
              <CardTitle className="text-[15px]">Error logs</CardTitle>
              <CardDescription>
                GET /logs?errors=true — last {errors.length} non-2xx org requests.
              </CardDescription>
            </CardHeader>
            <CardContent className="pb-[22px]">
              {errors.length === 0 ? (
                <Empty className="mt-[18px] min-h-[120px] border border-dashed">
                  <EmptyHeader>
                    <EmptyTitle>No error logs</EmptyTitle>
                    <EmptyDescription>No non-2xx rows in this range (or logs unavailable).</EmptyDescription>
                  </EmptyHeader>
                </Empty>
              ) : (
                <div className="mt-4 overflow-auto">
                  <table className="w-full text-left text-[13px]">
                    <thead className="font-mono text-[11px] tracking-[0.06em] text-muted-foreground uppercase">
                      <tr>
                        <th className="pb-2 font-medium">Time</th>
                        <th className="pb-2 font-medium">Model</th>
                        <th className="pb-2 font-medium">Status</th>
                        <th className="pb-2 text-right font-medium">Latency</th>
                        <th className="pb-2 text-right font-medium">Cost</th>
                      </tr>
                    </thead>
                    <tbody>
                      {errors.map((row, i) => (
                        <tr key={`${row.ts}-${i}`} className="border-t border-border">
                          <td className="py-2">{shortTs(row.ts)}</td>
                          <td className="py-2 font-mono text-[12.5px]">{row.selected || "—"}</td>
                          <td className="py-2">{row.status}</td>
                          <td className="py-2 text-right">{row.latency_ms} ms</td>
                          <td className="py-2 text-right font-mono text-[12.5px]">{usd(row.cost_usd)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
