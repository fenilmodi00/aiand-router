import type { Candidate, CandidateMix, Inference, Overview, Range, UsageBucket } from "./types";
import { EMPTY_OVERVIEW } from "./types";

/** Catalog Flash prices (USD / 1M). Default medium pick; used only to price "with router". */
const FLASH_IN = 0.15;
const FLASH_CACHED = 0.08;
const FLASH_OUT = 0.25;

type TsPoint = { timestamp?: string; value?: number; tokens?: number };
type MetricSeries = { metric_name?: string; timeseries?: TsPoint[] };
type LogRow = {
  id?: string;
  model?: string;
  status_code?: number;
  ttft_ms?: number | null;
  latency_ms?: number;
  input_tokens?: number;
  output_tokens?: number;
  cached_tokens?: number | null;
  cost?: string | number;
  created_at?: string;
};

export function flashUsd(input: number, output: number, cached = 0): number {
  const c = Math.max(0, Math.min(cached, input));
  return ((input - c) * FLASH_IN + c * FLASH_CACHED + output * FLASH_OUT) / 1_000_000;
}

function num(v: unknown): number {
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : 0;
}

function isoTs(raw: string): string {
  const s = raw.includes("T") ? raw : raw.replace(" ", "T");
  const d = new Date(s);
  return Number.isNaN(d.getTime()) ? raw : d.toISOString();
}

function displayName(id: string, names: Record<string, string>): string {
  if (names[id]) return names[id];
  const tail = id.split("/").pop() || id;
  return tail.replace(/-/g, " ");
}

export function parseSummary(data: unknown): { requests: number; input_tokens: number; output_tokens: number } {
  const obj = data && typeof data === "object" ? (data as Record<string, unknown>) : {};
  const cur =
    obj.current && typeof obj.current === "object" ? (obj.current as Record<string, unknown>) : obj;
  return {
    requests: num(cur.requests),
    input_tokens: num(cur.input_tokens),
    output_tokens: num(cur.output_tokens),
  };
}

export function parseLogs(data: unknown): LogRow[] {
  const arr = Array.isArray(data)
    ? data
    : data && typeof data === "object" && Array.isArray((data as { data?: unknown }).data)
      ? ((data as { data: unknown[] }).data)
      : [];
  return arr.filter((r): r is LogRow => !!r && typeof r === "object");
}

type TokenBucket = { ts: string; requests: number; input_tokens: number; output_tokens: number };

export function parseMetricBuckets(data: unknown): TokenBucket[] {
  const series: MetricSeries[] = Array.isArray((data as { data?: unknown })?.data)
    ? ((data as { data: MetricSeries[] }).data)
    : Array.isArray((data as { buckets?: unknown })?.buckets)
      ? []
      : [];
  const byTs = new Map<string, TokenBucket>();
  for (const s of series) {
    const key = s.metric_name;
    if (key !== "requests" && key !== "input_tokens" && key !== "output_tokens") continue;
    for (const p of s.timeseries || []) {
      const ts = String(p.timestamp || "");
      if (!ts) continue;
      const row = byTs.get(ts) || { ts, requests: 0, input_tokens: 0, output_tokens: 0 };
      row[key] = num(p.value);
      byTs.set(ts, row);
    }
  }
  if (byTs.size) return [...byTs.values()].sort((a, b) => a.ts.localeCompare(b.ts));

  const buckets = Array.isArray((data as { buckets?: unknown })?.buckets)
    ? ((data as { buckets: Record<string, unknown>[] }).buckets)
    : [];
  return buckets.map((b) => ({
    ts: String(b.ts || b.timestamp || ""),
    requests: num(b.requests),
    input_tokens: num(b.input_tokens),
    output_tokens: num(b.output_tokens),
  }));
}

function rollup(rows: TokenBucket[], max = 32): TokenBucket[] {
  if (rows.length <= max) return rows;
  const groups = new Map<string, TokenBucket>();
  for (const r of rows) {
    const day = r.ts.slice(0, 10) || r.ts;
    const g = groups.get(day) || { ts: `${day}T00:00:00.000Z`, requests: 0, input_tokens: 0, output_tokens: 0 };
    g.requests += r.requests;
    g.input_tokens += r.input_tokens;
    g.output_tokens += r.output_tokens;
    groups.set(day, g);
  }
  return [...groups.values()].sort((a, b) => a.ts.localeCompare(b.ts));
}

/** Assign each log to the latest metrics bucket whose ts is <= the log. */
function mixByBucket(logs: LogRow[], buckets: TokenBucket[]): Record<string, number>[] {
  const mixes: Record<string, number>[] = buckets.map(() => ({}));
  if (!buckets.length) return mixes;
  const times = buckets.map((b) => new Date(isoTs(b.ts)).getTime());
  for (const row of logs) {
    if (!row.created_at) continue;
    const t = new Date(isoTs(row.created_at)).getTime();
    if (!Number.isFinite(t)) continue;
    let i = 0;
    while (i + 1 < times.length && times[i + 1]! <= t) i += 1;
    const id = row.model || "unknown";
    mixes[i]![id] = (mixes[i]![id] || 0) + 1;
  }
  return mixes;
}

export function logToInference(row: LogRow): Inference {
  const cached = num(row.cached_tokens);
  return {
    ts: row.created_at ? isoTs(row.created_at) : null,
    selected: row.model || null,
    phase: null,
    tokens_in: num(row.input_tokens),
    tokens_out: num(row.output_tokens),
    latency_ms: Math.round(num(row.latency_ms)),
    status: Math.round(num(row.status_code)),
    cache_hit: cached > 0,
    path: "not-routed",
    cost_usd: num(row.cost),
    ttft_ms: row.ttft_ms == null ? null : Math.round(num(row.ttft_ms)),
    llmaj_score: null,
    tests_passed: null,
  };
}

export function overlayOverview(opts: {
  range: Range;
  summary: unknown;
  metrics: unknown;
  logs: unknown;
  catalog?: Candidate[];
}): Overview {
  const summary = parseSummary(opts.summary);
  const logs = parseLogs(opts.logs);
  const names = Object.fromEntries((opts.catalog || []).map((c) => [c.id, c.display_name]));

  let sampleSpend = 0;
  let sampleTokens = 0;
  let errors = 0;
  let cacheHits = 0;
  const counts: Record<string, number> = {};
  for (const row of logs) {
    const input = num(row.input_tokens);
    const output = num(row.output_tokens);
    sampleSpend += num(row.cost);
    sampleTokens += input + output;
    if (num(row.status_code) >= 400) errors += 1;
    if (num(row.cached_tokens) > 0) cacheHits += 1;
    const id = row.model || "unknown";
    counts[id] = (counts[id] || 0) + 1;
  }

  const n = logs.length;
  // ponytail: scale last ~200 log costs across metrics tokens; paginate all logs if mix drifts
  const costPerToken = sampleTokens > 0 ? sampleSpend / sampleTokens : 0;
  const tokenBuckets = rollup(parseMetricBuckets(opts.metrics));
  const metricTotals = tokenBuckets.reduce(
    (a, b) => ({
      requests: a.requests + b.requests,
      input_tokens: a.input_tokens + b.input_tokens,
      output_tokens: a.output_tokens + b.output_tokens,
    }),
    { requests: 0, input_tokens: 0, output_tokens: 0 },
  );
  const requests = summary.requests || metricTotals.requests;
  const inputTokens = summary.input_tokens || metricTotals.input_tokens;
  const outputTokens = summary.output_tokens || metricTotals.output_tokens;
  const fullTokens = inputTokens + outputTokens;
  const spend = n ? costPerToken * fullTokens : 0;
  const routerEst = flashUsd(inputTokens, outputTokens);
  const unsaved = Math.max(0, spend - routerEst);
  const baseline = spend;
  const routedEst = Math.min(routerEst, baseline);

  const mixes = mixByBucket(logs, tokenBuckets);
  const usage_buckets: UsageBucket[] = tokenBuckets.map((b, i) => {
    const tokens = b.input_tokens + b.output_tokens;
    const actual = costPerToken * tokens;
    const cheap = flashUsd(b.input_tokens, b.output_tokens);
    return {
      ts: isoTs(b.ts),
      requests: b.requests,
      by_model: mixes[i] || {},
      spend_usd: Math.min(cheap, actual),
      baseline_usd: actual,
    };
  });

  const mixIds = [...new Set([...(opts.catalog || []).map((c) => c.id), ...Object.keys(counts)])];
  const candidate_mix: CandidateMix[] = mixIds.map((id) => ({
    id,
    display_name: displayName(id, names),
    count: counts[id] || 0,
    pct: n ? (100 * (counts[id] || 0)) / n : 0,
  }));
  const candidates: Candidate[] = mixIds.map((id) => ({
    id,
    display_name: displayName(id, names),
    enabled: true,
  }));

  return {
    ...EMPTY_OVERVIEW,
    range: opts.range,
    routed_requests: requests,
    spend_usd: spend,
    savings_usd: 0,
    savings_pct: 0,
    unsaved_usd: unsaved,
    fallback_count: errors,
    fallback_rate: n ? errors / n : 0,
    cache_hits: cacheHits,
    aiand_key_set: true,
    candidates,
    candidate_mix,
    usage_buckets,
    cost_routed_usd: routedEst,
    cost_baseline_usd: baseline,
    org_overlay: true,
    org_sample_n: n,
    org_input_tokens: inputTokens,
    org_output_tokens: outputTokens,
  };
}
