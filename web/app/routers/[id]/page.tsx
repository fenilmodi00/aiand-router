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
import { getInferences, getOrgUsage, getOverview, maskKey } from "@/lib/api";
import { compact, parseRange, pct, RANGE_LABEL, usd } from "@/lib/format";
import type { Range } from "@/lib/types";

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
  // Prefer AIand org analytics whenever it has more traffic than the local hop log.
  // Local-only was wrong after a key rotate / one playground hop: UI stuck on 1 while org had 100s.
  const useOrg =
    orgRes.ok && !!org && org.routed_requests > 0 && org.routed_requests > (local.routed_requests || 0);
  const o = useOrg && org ? org : local;
  const inferences = useOrg ? (orgRes.data?.inferences ?? []) : (inferencesRes.data?.data ?? []);
  const n = o.candidates.filter((c) => c.enabled).length || o.candidates.length;
  const rows = mixRows(o.candidates, o.candidate_mix);
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
    <div className="mx-auto max-w-[1360px] px-6 md:px-11 pt-[26px] pb-[120px] bg-black text-white">
      {/* Top Breadcrumb */}
      <nav className="mb-6 flex items-center gap-2 text-[13px] text-[#71717a]" aria-label="Breadcrumb">
        <Link href="/routers" className="inline-flex size-[22px] items-center justify-center rounded-md text-[#71717a] hover:bg-[#141417] hover:text-white" aria-label="Back to routers">
          <ChevronLeftIcon className="size-3.5" />
        </Link>
        <Link href="/routers" className="hover:text-white">Routers</Link>
        <span className="text-[#3f3f46]">/</span>
        <span className="font-semibold text-white">aiand/auto</span>
      </nav>

      {/* 1. TOP HERO DUO GRID */}
      <section className="mb-10 grid gap-6 lg:grid-cols-[1.22fr_1fr]">
        <Card className="flex flex-col gap-0 rounded-2xl border border-[#1a1a1e] bg-[#08080a] p-8 shadow-xs">
          <CardHeader className="p-0">
            <CardTitle className="text-[28px] font-semibold tracking-tight text-white">Inference aiand/auto</CardTitle>
            <CardDescription className="mt-2 font-mono text-[11px] tracking-[0.08em] uppercase text-[#71717a]">
              ROUTER · AUTO · {n} CANDIDATES
            </CardDescription>
          </CardHeader>
          <CardContent className="mt-3 p-0 text-[13.5px] text-[#8e8e96]">
            Integrate <strong className="font-semibold text-white">aiand/auto</strong> into your stack
          </CardContent>
          <div className="mt-auto flex flex-wrap items-center gap-3 pt-12">
            <Button render={<Link href="/playground" />} nativeButton={false} variant="outline" className="h-9 rounded-lg border border-[#27272a] bg-[#0c0c0e] px-4 text-xs font-medium text-white hover:bg-[#17171a]">
              Try in playground
            </Button>
            <Button render={<a href="https://docs.aiand.com/" target="_blank" rel="noreferrer" />} nativeButton={false} variant="outline" className="h-9 rounded-lg border border-[#27272a] bg-[#0c0c0e] px-4 text-xs font-medium text-white hover:bg-[#17171a]">
              Docs
            </Button>
            <Button render={<a href="#run-inference" />} nativeButton={false} className="h-9 rounded-lg bg-white px-12 text-xs font-semibold text-black hover:bg-neutral-200">
              Integrate
            </Button>
          </div>
        </Card>

        <div className="flex flex-col gap-4">
          <Card className="rounded-2xl border border-[#1a1a1e] bg-[#08080a] gap-0 py-0 shadow-xs">
            <CardHeader className="flex flex-row items-center justify-between pt-4 pb-2 px-5">
              <CardTitle className="flex items-center gap-2 text-[12.5px] font-medium text-[#8e8e96]">
                <KeyRoundIcon className="size-3.5" />
                API Key
              </CardTitle>
              <CardAction>
                <Link href="/keys" className="text-[12px] text-[#71717a] hover:text-white transition">
                  View all
                </Link>
              </CardAction>
            </CardHeader>
            <CardContent className="pb-4 px-5">
              <KeyPill masked={maskKey()} />
            </CardContent>
          </Card>

          <Card className="flex flex-1 flex-col rounded-2xl border border-[#1a1a1e] bg-[#08080a] gap-0 py-0 shadow-xs">
            <CardHeader className="flex flex-row items-center justify-between pt-4 pb-2 px-5">
              <CardTitle className="flex items-center gap-2 text-[12.5px] font-medium text-[#8e8e96]">
                <BarChart3Icon className="size-3.5" />
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
            <CardContent className="pb-4 px-5">
              <UsageChart buckets={o.usage_buckets} candidates={o.candidates} />
            </CardContent>
          </Card>
        </div>
      </section>

      {/* 2. OVERVIEW HEADER + TIME RANGE MENU */}
      <div className="mt-10 mb-4 flex items-center justify-between">
        <h2 className="text-[17px] font-semibold text-white">Overview</h2>
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
            Showing live account usage from{" "}
            <a href="https://docs.aiand.com/analytics/metrics/" className="underline">
              AIand analytics
            </a>{" "}
            ({o.routed_requests} requests
            {o.org_sample_n ? `, ${o.org_sample_n} detailed logs` : ""}
            {local.routed_requests > 0 ? `; this gateway logged ${local.routed_requests} local hop(s)` : ""}
            ). Spend uses billed log costs when the log sample covers token volume; otherwise it is
            scaled. You saved {usd(0)}; you have not saved {usd(o.unsaved_usd)} versus Flash.
          </AlertDescription>
        </Alert>
      ) : !orgRes.ok && local.routed_requests === 0 ? (
        <Alert className="mb-4">
          <AlertTitle>AIand org usage unavailable</AlertTitle>
          <AlertDescription>{orgRes.error}. Set DATA_AIAND_API_KEY in web/.env.local.</AlertDescription>
        </Alert>
      ) : null}

      {/* 3. 4 STATCARDS (PIONEER-STYLE) */}
      <div className="grid gap-[18px] sm:grid-cols-2 lg:grid-cols-4 mb-6">
        <StatCard
          label={useOrg ? "ORG REQUESTS" : "ROUTED REQUESTS"}
          value={String(o.routed_requests)}
          sub={
            useOrg
              ? `${compact(o.org_input_tokens)} in · ${compact(o.org_output_tokens)} out`
              : (o.routed_requests > 0 && o.input_tokens ? `${compact(o.input_tokens)} in · ${compact(o.output_tokens || 0)} out` : undefined)
          }
        />
        <StatCard
          label={useOrg ? "NOT SAVED" : "SAVINGS"}
          value={usd(useOrg ? o.unsaved_usd : o.savings_usd)}
          sub={
            useOrg
              ? `${usd(o.cost_routed_usd)} with router · est.`
              : `${usd(o.spend_usd + o.savings_usd)}`
          }
          green={!useOrg && o.savings_usd > 0}
        />
        <StatCard
          label={useOrg ? "ERROR RATE" : "FALLBACK RATE"}
          value={pct(o.fallback_rate * 100)}
          sub={
            useOrg
              ? `${o.fallback_count} of last ${o.org_sample_n} logs`
              : `${o.fallback_count} of ${o.routed_requests}`
          }
        />
        <StatCard
          label={useOrg ? "YOUR SPEND" : "CANDIDATES"}
          value={useOrg ? usd(o.spend_usd) : String(n)}
          sub={
            useOrg
              ? (o.org_sample_n ? `from ${o.org_sample_n} billed logs` : "from AIand logs")
              : "configured models"
          }
        />
      </div>

      {/* 4. COST VS BASELINE + CANDIDATE MIX DUO GRID */}
      <div className="grid gap-[18px] lg:grid-cols-2 mb-6">
        <CostVsBaseline
          buckets={o.usage_buckets}
          savingsUsd={useOrg ? o.unsaved_usd : o.savings_usd}
          savingsPct={useOrg ? (o.spend_usd > 0 ? (100 * o.unsaved_usd) / o.spend_usd : 0) : o.savings_pct}
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

      {/* 5. ROUTER SAVINGS STEP CHART */}
      <div className="mb-6">
        <RouterSavingsChart buckets={o.usage_buckets} unrealized={useOrg} />
      </div>

      {/* 6. ROUTING PIPELINE DIAGNOSTICS */}
      <div className="mb-8">
        <RoutingPipeline
          requests={useOrg ? o.org_sample_n : o.routed_requests}
          rows={rows}
          savingsUsd={useOrg ? o.unsaved_usd : o.savings_usd}
          savingsPct={o.savings_pct}
          routerName="aiand/auto"
        />
      </div>

      {/* 6. RUN AN INFERENCE QUICKSTART */}
      <div id="run-inference" className="mt-10 mb-4">
        <h2 className="text-[17px] font-semibold text-white">Run an inference</h2>
      </div>
      <InferenceSnippet />

      {/* 7. INFERENCES LOGS TABLE */}
      <div className="mt-10 mb-4">
        <h2 className="text-[17px] font-semibold text-white">Inferences</h2>
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
