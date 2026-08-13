import Link from "next/link";
import { notFound } from "next/navigation";
import { InferenceSnippet } from "@/components/InferenceSnippet";
import { InferencesTable } from "@/components/InferencesTable";
import { KeyPill } from "@/components/KeyPill";
import { mixRows, RoutingPipeline } from "@/components/RoutingPipeline";
import { RouterSavingsChart } from "@/components/RouterSavingsChart";
import { StatCard } from "@/components/StatCard";
import { UsageChart } from "@/components/UsageChart";
import { getInferences, getOverview, maskKey } from "@/lib/api";
import { parseRange, pct, RANGE_LABEL, usd } from "@/lib/format";
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

  const [overviewRes, inferencesRes] = await Promise.all([
    getOverview(range),
    getInferences(range, q, model),
  ]);
  const o = overviewRes.data!;
  const inferences = inferencesRes.data?.data ?? [];
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

  return (
    <div className="content">
      <nav className="breadcrumb" aria-label="Breadcrumb">
        <Link className="back" href="/routers" aria-label="Back to routers">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M15 6l-6 6 6 6" />
          </svg>
        </Link>
        <Link href="/routers">Routers</Link>
        <span className="sep">/</span>
        <span className="current">router/auto</span>
      </nav>

      <section className="hero">
        <div className="card hero-main">
          <h1>Inference router/auto</h1>
          <div className="hero-meta">{meta}</div>
          <p className="hero-desc">
            Integrate <strong>router/auto</strong> into your stack
          </p>
          <div className="hero-actions">
            <Link className="btn" href="/playground">
              Try in playground
            </Link>
            <a className="btn" href="https://docs.aiand.com/" target="_blank" rel="noreferrer">
              Docs
            </a>
            <a className="btn btn-primary" href="#run-inference">
              Integrate
            </a>
          </div>
        </div>
        <div className="hero-side">
          <div className="card card-pad">
            <div className="field-head">
              <span className="left">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                  <circle cx="8" cy="15" r="4" />
                  <path d="M11 12l9-9M17 4l3 3M14 7l3 3" />
                </svg>
                API Key
              </span>
              <Link href="/keys">View all</Link>
            </div>
            <KeyPill masked={maskKey()} />
          </div>
          <div className="card card-pad" style={{ flex: 1 }}>
            <div className="field-head">
              <span className="left">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                  <path d="M4 20V10M10 20V4M16 20v-8M22 20H2" />
                </svg>
                Usage
              </span>
              <span className="seg">
                <Link className={range === "24h" ? "on" : ""} href={qs("24h")}>
                  24h
                </Link>
                <Link className={range === "30d" ? "on" : ""} href={qs("30d")}>
                  30d
                </Link>
              </span>
            </div>
            <UsageChart buckets={o.usage_buckets} candidates={o.candidates} />
          </div>
        </div>
      </section>

      <div className="section-head">
        <h2>Overview</h2>
        <details className="menu-wrap">
          <summary className="btn btn-sm">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
              <rect x="3" y="5" width="18" height="16" rx="2" />
              <path d="M3 10h18M8 3v4M16 3v4" />
            </svg>
            <span>{RANGE_LABEL[range]}</span>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M6 9l6 6 6-6" />
            </svg>
          </summary>
          <div className="menu">
            {(Object.keys(RANGE_LABEL) as Range[]).map((r) => (
              <Link key={r} className={r === range ? "on" : ""} href={qs(r)}>
                {RANGE_LABEL[r]}
              </Link>
            ))}
          </div>
        </details>
      </div>

      {overviewRes.error && !overviewRes.ok ? (
        <div className="empty" style={{ height: 48, marginBottom: 16 }}>
          Console overview unavailable ({overviewRes.error}). Empty zeros below.
        </div>
      ) : null}

      <div className="stats">
        <StatCard label="Routed requests" value={String(o.routed_requests)} />
        <StatCard label="Savings" value={usd(o.savings_usd)} sub={pct(o.savings_pct)} green />
        <StatCard
          label="Fallback rate"
          value={pct(o.fallback_rate * 100)}
          sub={`${o.fallback_count} of ${o.routed_requests}`}
        />
        <StatCard label="Candidates" value={String(n)} sub="configured models" />
      </div>

      <div className="card card-pad" style={{ marginTop: 18 }}>
        <RouterSavingsChart buckets={o.usage_buckets} />
      </div>

      <div className="card card-pad" style={{ marginTop: 18 }}>
        <div className="card-title">Candidate mix</div>
        <div className="card-sub">Which models the router picked across the last {o.routed_requests} routed requests.</div>
        {!hasMix ? (
          <div className="empty" style={{ height: 150, marginTop: 18 }}>
            No routed requests yet.
          </div>
        ) : (
          rows
            .filter((r) => r.count > 0)
            .map((r) => (
              <div className="meter-row" key={r.id}>
                <div className="row-head">
                  <span>{r.display_name}</span>
                  <span className="v">
                    {r.count} · {pct(r.pct)}
                  </span>
                </div>
                <div className="track">
                  <div className="fill" style={{ width: `${Math.min(100, r.pct)}%` }} />
                </div>
              </div>
            ))
        )}
      </div>

      <div className="section-head">
        <div>
          <h2>Routing pipeline</h2>
          <div className="card-sub">How the last {o.routed_requests} routed requests flowed to each candidate model.</div>
        </div>
      </div>
      <RoutingPipeline requests={o.routed_requests} rows={rows} />

      <div className="card card-pad" style={{ marginTop: 18 }}>
        <div className="field-head" style={{ marginBottom: 18 }}>
          <span>
            <div className="card-title">Quality over time</div>
            <div className="card-sub">
              {judged.length ? "Flashlight test outcome" : "No judge data yet"}
            </div>
          </span>
          <span className="ranges">
            {QUALITY_RANGES.map((r) => (
              <Link key={r.id} className={range === r.id ? "on" : ""} href={qs(r.id)}>
                {r.label}
              </Link>
            ))}
          </span>
        </div>
        {judged.length === 0 ? (
          <div className="empty" style={{ height: 200 }}>
            No judge data yet
          </div>
        ) : (
          <div>
            <div className="stats" style={{ gridTemplateColumns: "repeat(2, 1fr)" }}>
              <StatCard label="Flashlight tests" value={`${passed} / ${judged.length}`} />
              <StatCard label="Pass rate" value={pct((passed / judged.length) * 100)} />
            </div>
            <p className="hint">This is the logged flashlight tests_passed flag, not an LLMaJ score.</p>
          </div>
        )}
        <div className="legend" style={{ marginTop: 14 }}>
          <span className="swatch" />
          {judged.length ? "Flashlight pass rate" : "Judge pass rate"}
        </div>
      </div>

      <div className="section-head">
        <h2 className="big">Run an inference</h2>
      </div>
      <InferenceSnippet />

      <div className="section-head">
        <h2 className="big">Inferences</h2>
      </div>
      <InferencesTable
        rows={inferences}
        range={range}
        q={q}
        model={model}
        candidates={o.candidates}
        error={inferencesRes.ok ? null : inferencesRes.error}
      />
    </div>
  );
}
