import Link from "next/link";
import { notFound } from "next/navigation";
import { BarChart3Icon, ChevronLeftIcon, KeyRoundIcon } from "lucide-react";
import { CandidateMixPioneer } from "@/components/CandidateMixPioneer";
import { CostVsBaseline } from "@/components/CostVsBaseline";
import { InferenceSnippet } from "@/components/InferenceSnippet";
import { InferencesTable } from "@/components/InferencesTable";
import { KeyPill } from "@/components/KeyPill";
import { LinkToggle, RangeMenu } from "@/components/RangeMenu";
import { mixRows, RoutingPipeline } from "@/components/RoutingPipeline";
import { RouterSavingsChart } from "@/components/RouterSavingsChart";
import { StatCard } from "@/components/StatCard";
import { UsageChart } from "@/components/UsageChart";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { getInferences, getOrgUsage, getOverview, maskKey } from "@/lib/api";
import { compact, parseRange, pct, RANGE_LABEL, usd } from "@/lib/format";
import type { Range } from "@/lib/types";

const QUALITY_RANGES: { id: Range; label: string }[] = [
  { id: "24h", label: "24hr" },
  { id: "7d", label: "7d" },
  { id: "30d", label: "30d" },
  { id: "all", label: "All" },
];

export default async function RouterDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ range?: string; q?: string; model?: string }>;
}) {
  const { id } = await params;
  if (id !== "auto") notFound();
  const sp = await searchParams;
  const range = parseRange(sp.range);
  const q = sp.q || "";
  const model = sp.model || "";

  const [overviewRes, inferencesRes, orgRes] = await Promise.all([
    getOverview(range),
    getInferences(range, q, model),
    getOrgUsage(range, q, model),
  ]);
  const local = overviewRes.data!;
  const org = orgRes.data?.overview;
  const useOrg = local.routed_requests === 0 && !!org && org.routed_requests > 0;
  const o = useOrg && org ? org : local;
  const inferences = useOrg ? (orgRes.data?.inferences ?? []) : (inferencesRes.data?.data ?? []);
  const n = o.candidates.filter((c) => c.enabled).length || o.candidates.length;
  const meta = n ? `Router · Auto · ${n} candidates` : "Router · Auto";
  const rows = mixRows(o.candidates, o.candidate_mix);
  const hasMix = o.routed_requests > 0 && rows.some((r) => r.count > 0);
  const judged = inferences.filter((r) => r.tests_passed !== null);
  const passed = judged.filter((r) => r.tests_passed).length;
  const qs = (next: Range) => {
    const p = new URLSearchParams();
    p.set("range", next);
    if (q) p.set("q", q);
    if (model) p.set("model", model);
    return `/routers/auto?${p}`;
  };
  const hrefs = Object.fromEntries((Object.keys(RANGE_LABEL) as Range[]).map((r) => [r, qs(r)])) as Record<
    Range,
    string
  >;

  return (
    <div className="mx-auto max-w-[1360px] px-11 pt-[26px] pb-[120px]">
      {/* Pioneer-style breadcrumb: back arrow + breadcrumb path */}
      <nav className="mb-[22px] flex items-center gap-2 text-[13px] text-muted-foreground" aria-label="Breadcrumb">
        <Link href="/routers" className="inline-flex size-[22px] items-center justify-center rounded-md hover:bg-[#17171a] hover:text-foreground" aria-label="Back to routers">
          <ChevronLeftIcon />
        </Link>
        <Link href="/routers" className="hover:text-foreground">Routers</Link>
        <span className="text-muted-foreground/50">/</span>
        <span className="text-[#d4d4d8]">router/auto</span>
      </nav>

      <section className="mb-10 grid gap-6 lg:grid-cols-[1.22fr_1fr]">
        <Card className="flex flex-col gap-0 px-9 py-[34px]">
          <CardHeader className="p-0">
            <CardTitle className="text-[29px] font-semibold tracking-tight">Inference router/auto</CardTitle>
            <CardDescription className="mt-3 font-mono text-[11px] tracking-[0.08em] uppercase">
              {meta}
            </CardDescription>
          </CardHeader>
          <CardContent className="mt-4 p-0 text-[13.5px] text-muted-foreground">
            Integrate <strong className="font-semibold text-foreground">router/auto</strong> into your stack
          </CardContent>
          <div className="mt-auto flex gap-3 pt-12">
            <Button render={<Link href="/playground" />} nativeButton={false} variant="outline" className="h-10">
              Try in playground
            </Button>
            <Button render={<a href="https://docs.aiand.com/" target="_blank" rel="noreferrer" />} nativeButton={false} variant="outline" className="h-10">
              Docs
            </Button>
            <Button render={<a href="#run-inference" />} nativeButton={false} className="h-10 px-16">
              Integrate
            </Button>
          </div>
        </Card>
        <div className="flex flex-col gap-6">
          <Card className="gap-0 py-0">
            <CardHeader className="flex flex-row items-center justify-between pt-[22px] pb-3.5">
              <CardTitle className="flex items-center gap-2 text-[13px] font-medium text-muted-foreground">
                <KeyRoundIcon />
                API Key
              </CardTitle>
              <CardAction>
                <Button render={<Link href="/keys" />} nativeButton={false} variant="link" size="sm" className="h-auto px-0">
                  View all
                </Button>
              </CardAction>
            </CardHeader>
            <CardContent className="pb-[22px]">
              <KeyPill masked={maskKey()} />
            </CardContent>
          </Card>
          <Card className="flex flex-1 flex-col gap-0 py-0">
            <CardHeader className="flex flex-row items-center justify-between pt-[22px] pb-3.5">
              <CardTitle className="flex items-center gap-2 text-[13px] font-medium text-muted-foreground">
                <BarChart3Icon />
                Usage
              </CardTitle>
              <CardAction>
                <LinkToggle
                  value={range === "24h" ? "24h" : "30d"}
                  items={[
                    { value: "24h", label: "24h", href: qs("24h") },
                    { value: "30d", label: "30d", href: qs("30d") },
                  ]}
                />
              </CardAction>
            </CardHeader>
            <CardContent className="pb-[22px]">
              <UsageChart buckets={o.usage_buckets} candidates={o.candidates} />
            </CardContent>
          </Card>
        </div>
      </section>

      <div className="mt-[42px] mb-[18px] flex items-center justify-between">
        <h2 className="text-base font-semibold">Overview</h2>
        <RangeMenu range={range} hrefs={hrefs} />
      </div>

      {overviewRes.error && !overviewRes.ok && !useOrg ? (
        <Alert className="mb-4">
          <AlertTitle>Console overview unavailable</AlertTitle>
          <AlertDescription>{overviewRes.error}. Empty zeros below.</AlertDescription>
        </Alert>
      ) : null}

      {useOrg ? (
        <Alert className="mb-4">
          <AlertTitle>AIand org traffic — not routed</AlertTitle>
          <AlertDescription>
            Inference is down, so this dashboard is showing existing org usage from{" "}
            <a href="https://docs.aiand.com/analytics/metrics/" className="underline">
              AIand analytics
            </a>
            , not hops through this router. Spend is estimated from recent logs × token volume. You
            saved {usd(0)}; you have not saved {usd(o.unsaved_usd)} versus Flash.
          </AlertDescription>
        </Alert>
      ) : !orgRes.ok && local.routed_requests === 0 ? (
        <Alert className="mb-4">
          <AlertTitle>AIand org usage unavailable</AlertTitle>
          <AlertDescription>{orgRes.error}. Set DATA_AIAND_API_KEY in web/.env.local.</AlertDescription>
        </Alert>
      ) : null}

      <div className="grid gap-[18px] sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label={useOrg ? "Org requests" : "Routed requests"}
          value={String(o.routed_requests)}
          sub={useOrg ? `${compact(o.org_input_tokens)} in · ${compact(o.org_output_tokens)} out` : undefined}
        />
        {useOrg ? (
          <StatCard
            label="Not saved"
            value={usd(o.unsaved_usd)}
            sub={`${usd(o.cost_routed_usd)} with router · est.`}
          />
        ) : (
          <StatCard label="Savings" value={usd(o.savings_usd)} sub={pct(o.savings_pct)} green />
        )}
        <StatCard
          label={useOrg ? "Error rate" : "Fallback rate"}
          value={pct(o.fallback_rate * 100)}
          sub={
            useOrg
              ? `${o.fallback_count} of last ${o.org_sample_n} logs`
              : `${o.fallback_count} of ${o.routed_requests}`
          }
        />
        <StatCard
          label={useOrg ? "Your spend" : "Candidates"}
          value={useOrg ? usd(o.spend_usd) : String(n)}
          sub={useOrg ? "est. from recent mix" : "configured models"}
        />
      </div>

      {/* Pioneer-style duo grid: Cost vs baseline + Candidate mix */}
      <div className="mt-[18px] grid gap-[18px] lg:grid-cols-2">
        <CostVsBaseline
          buckets={o.usage_buckets}
          savingsUsd={o.savings_usd}
          savingsPct={o.savings_pct}
          unrealized={useOrg}
        />
        <CandidateMixPioneer
          rows={rows}
          total={o.routed_requests}
          emptyLabel="No routed requests yet."
          useOrg={useOrg}
          orgSampleN={o.org_sample_n}
        />
      </div>

      {/* Detailed savings step chart (beyond Pioneer's simple meter) */}
      <div className="mt-[18px]">
        <RouterSavingsChart buckets={o.usage_buckets} unrealized={useOrg} />
      </div>

      <div className="mt-[42px] mb-[18px]">
        <h2 className="text-base font-semibold">Routing pipeline</h2>
        <p className="mt-1 text-[13px] text-muted-foreground">
          {useOrg
            ? `How the last ${o.org_sample_n} org requests were sent directly to models, skipping the router.`
            : `How the last ${o.routed_requests} routed requests flowed to each candidate model.`}
        </p>
      </div>
      <RoutingPipeline requests={useOrg ? o.org_sample_n : o.routed_requests} rows={rows} />

      <Card className="mt-[18px] gap-0 py-0">
        <CardHeader className="flex flex-row items-start justify-between pt-[22px]">
          <div>
            <CardTitle>Quality over time</CardTitle>
            <CardDescription>{judged.length ? "Flashlight test outcome" : "No judge data yet"}</CardDescription>
          </div>
          <CardAction>
            <LinkToggle
              value={range}
              items={QUALITY_RANGES.map((r) => ({ value: r.id, label: r.label, href: qs(r.id) }))}
            />
          </CardAction>
        </CardHeader>
        <CardContent className="pb-[22px]">
          {judged.length === 0 ? (
            <Empty className="min-h-[200px] border border-dashed">
              <EmptyHeader>
                <EmptyTitle>No judge data yet</EmptyTitle>
                <EmptyDescription>Flashlight tests have not been recorded for this range.</EmptyDescription>
              </EmptyHeader>
            </Empty>
          ) : (
            <div className="flex flex-col gap-3">
              <div className="grid gap-[18px] sm:grid-cols-2">
                <StatCard label="Flashlight tests" value={`${passed} / ${judged.length}`} />
                <StatCard label="Pass rate" value={pct((passed / judged.length) * 100)} />
              </div>
              <p className="text-[13px] text-muted-foreground">
                This is the logged flashlight tests_passed flag, not an LLMaJ score.
              </p>
            </div>
          )}
          <div className="mt-3.5 flex items-center gap-2 text-xs text-muted-foreground">
            <span className="h-0.5 w-[18px] rounded-sm bg-success" />
            {judged.length ? "Flashlight pass rate" : "Judge pass rate"}
          </div>
        </CardContent>
      </Card>

      <div className="mt-[42px] mb-[18px]">
        <h2 className="text-xl font-semibold">Run an inference</h2>
      </div>
      <InferenceSnippet />

      <div className="mt-[42px] mb-[18px]">
        <h2 className="text-xl font-semibold">Inferences</h2>
      </div>
      <InferencesTable
        rows={inferences}
        range={range}
        q={q}
        model={model}
        candidates={o.candidates}
        error={useOrg ? (orgRes.ok ? null : orgRes.error) : inferencesRes.ok ? null : inferencesRes.error}
      />
    </div>
  );
}
