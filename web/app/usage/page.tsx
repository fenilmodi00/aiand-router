import Link from "next/link";
import { getHealth, getOverview, getUpstream } from "@/lib/api";
import { parseRange, pct, RANGE_LABEL, usd } from "@/lib/format";
import { StatCard } from "@/components/StatCard";
import type { Range } from "@/lib/types";

function headlines(data: unknown): { label: string; value: string }[] {
  if (!data || typeof data !== "object") return [];
  const obj = data as Record<string, unknown>;
  const nested =
    obj.summary && typeof obj.summary === "object"
      ? (obj.summary as Record<string, unknown>)
      : obj.data && typeof obj.data === "object" && !Array.isArray(obj.data)
        ? (obj.data as Record<string, unknown>)
        : obj;
  const out: { label: string; value: string }[] = [];
  for (const [k, v] of Object.entries(nested)) {
    if (v == null || Array.isArray(v) || (typeof v === "object" && v !== null)) continue;
    out.push({ label: k.replace(/_/g, " "), value: String(v) });
    if (out.length >= 12) break;
  }
  return out;
}

function series(data: unknown): { ts: string; n: number }[] {
  if (!data) return [];
  const arr = Array.isArray(data)
    ? data
    : data && typeof data === "object" && Array.isArray((data as { data?: unknown }).data)
      ? ((data as { data: unknown[] }).data)
      : data && typeof data === "object" && Array.isArray((data as { metrics?: unknown }).metrics)
        ? ((data as { metrics: unknown[] }).metrics)
        : [];
  return arr.slice(0, 48).map((row, i) => {
    const r = row as Record<string, unknown>;
    const ts = String(r.ts ?? r.timestamp ?? r.t ?? i);
    const n = Number(r.requests ?? r.count ?? r.tokens ?? r.spend_usd ?? r.value ?? 0);
    return { ts, n: Number.isFinite(n) ? n : 0 };
  });
}

export default async function UsagePage({
  searchParams,
}: {
  searchParams: Promise<{ range?: string }>;
}) {
  const range = parseRange((await searchParams).range);
  const [overviewRes, healthRes, summaryRes, metricsRes, logsRes] = await Promise.all([
    getOverview(range),
    getHealth(),
    getUpstream("summary", range),
    getUpstream("metrics", range),
    getUpstream("logs", range),
  ]);
  const o = overviewRes.data!;
  const h = healthRes.data!;
  const summaryLines = headlines(summaryRes.data);
  const metricRows = series(metricsRes.data);
  const maxM = Math.max(1, ...metricRows.map((r) => r.n));
  const qs = (r: Range) => `/usage?range=${r}`;

  return (
    <div className="content">
      <div className="section-head" style={{ marginTop: 0 }}>
        <div>
          <h2 className="big">Usage</h2>
          <div className="card-sub">Local router hops vs AIand org analytics. These layers are not the same traffic.</div>
        </div>
        <details className="menu-wrap">
          <summary className="btn btn-sm">{RANGE_LABEL[range]}</summary>
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

      <div className="section-head" style={{ marginTop: 12 }}>
        <h2>This router</h2>
      </div>
      <div className="stats">
        <StatCard label="Routed requests" value={String(o.routed_requests)} />
        <StatCard label="Spend" value={usd(h.spend_usd || o.spend_usd)} sub={`budget ${usd(h.budget_usd || o.budget_usd)}`} />
        <StatCard label="Savings" value={usd(o.savings_usd)} sub={pct(o.savings_pct)} green />
        <StatCard label="Cache hits" value={String(o.cache_hits)} />
      </div>

      <div className="section-head">
        <h2>AIand org</h2>
      </div>
      <div className="duo">
        <div className="card card-pad">
          <div className="card-title">Summary</div>
          <div className="card-sub">GET /v1/console/upstream/summary</div>
          {!summaryRes.ok ? (
            <div className="empty" style={{ height: 150, marginTop: 18 }}>
              AIand analytics unavailable ({summaryRes.error || summaryRes.status || "error"}).
            </div>
          ) : summaryLines.length === 0 ? (
            <div className="empty" style={{ height: 150, marginTop: 18 }}>
              No summary fields.
            </div>
          ) : (
            summaryLines.map((s) => (
              <div className="meter-row" key={s.label}>
                <div className="row-head">
                  <span>{s.label}</span>
                  <span className="v">{s.value}</span>
                </div>
              </div>
            ))
          )}
        </div>
        <div className="card card-pad">
          <div className="card-title">Metrics</div>
          <div className="card-sub">GET /v1/console/upstream/metrics</div>
          {!metricsRes.ok ? (
            <div className="empty" style={{ height: 150, marginTop: 18 }}>
              AIand metrics unavailable ({metricsRes.error || metricsRes.status || "error"}).
            </div>
          ) : metricRows.length === 0 ? (
            <div className="empty" style={{ height: 150, marginTop: 18 }}>
              No metrics series.
            </div>
          ) : (
            <svg viewBox="0 0 560 180" width="100%" role="img" aria-label="AIand metrics" style={{ marginTop: 12 }}>
              <g stroke="#26262b" strokeDasharray="4 5">
                <line x1="20" y1="160" x2="540" y2="160" />
                <line x1="20" y1="80" x2="540" y2="80" />
                <line x1="20" y1="10" x2="540" y2="10" />
              </g>
              {metricRows.map((row, i) => {
                const slot = 520 / metricRows.length;
                const hgt = (row.n / maxM) * 140;
                return (
                  <rect
                    key={`${row.ts}-${i}`}
                    x={20 + i * slot + 2}
                    y={160 - hgt}
                    width={Math.max(4, slot - 4)}
                    height={hgt}
                    fill="#2dd4bf"
                    rx="2"
                  />
                );
              })}
            </svg>
          )}
        </div>
      </div>

      <div className="card card-pad" style={{ marginTop: 18 }}>
        <div className="card-title">Logs</div>
        <div className="card-sub">GET /v1/console/upstream/logs — cached_tokens / ttft when the proxy returns them.</div>
        {!logsRes.ok ? (
          <div className="empty" style={{ height: 120, marginTop: 18 }}>
            AIand logs unavailable ({logsRes.error || logsRes.status || "error"}).
          </div>
        ) : (
          <pre className="pg-out" style={{ marginTop: 16, maxHeight: 280, overflow: "auto" }}>
            {JSON.stringify(logsRes.data, null, 2) || "[]"}
          </pre>
        )}
      </div>
    </div>
  );
}
