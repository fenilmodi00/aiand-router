import "server-only";

import { logToInference, overlayOverview, parseLogs } from "./aiand";
import {
  EMPTY_HEALTH,
  EMPTY_OVERVIEW,
  type FetchResult,
  type Health,
  type Inference,
  type Inferences,
  type MaskedKey,
  type ModelsResponse,
  type Overview,
  type Range,
} from "./types";

export type OrgBundle = {
  overview: Overview;
  inferences: Inference[];
  errors: Inference[];
};

function baseUrl(): string {
  return (process.env.ROUTER_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
}

function authHeader(): string {
  return `Bearer ${process.env.ROUTER_API_KEY || ""}`;
}

/** AIand analytics/logs want 7days/30days. Overview/inferences keep 24h|7d|30d|all. */
export function toAiandRange(range: Range): string {
  if (range === "7d") return "7days";
  if (range === "30d" || range === "all") return "30days";
  return "24h";
}

function errorMessage(status: number, statusText: string, body: unknown): string {
  if (body && typeof body === "object") {
    const o = body as Record<string, unknown>;
    if (typeof o.error === "string") return o.error;
    if (typeof o.detail === "string") return o.detail;
  }
  return `${status} ${statusText}`;
}

function coerceOverview(data: Partial<Overview> | null, range: Range): Overview {
  return {
    ...EMPTY_OVERVIEW,
    ...data,
    range: data?.range || range,
    candidates: data?.candidates ?? [],
    candidate_mix: data?.candidate_mix ?? [],
    usage_buckets: data?.usage_buckets ?? [],
    unsaved_usd: data?.unsaved_usd ?? 0,
    org_overlay: data?.org_overlay ?? false,
    org_sample_n: data?.org_sample_n ?? 0,
    org_input_tokens: data?.org_input_tokens ?? 0,
    org_output_tokens: data?.org_output_tokens ?? 0,
  };
}

function coerceInference(row: Inference): Inference {
  return {
    ...row,
    ts: row.ts ?? null,
    selected: row.selected ?? null,
    phase: row.phase ?? null,
    ttft_ms: row.ttft_ms ?? null,
    llmaj_score: row.llmaj_score ?? null,
    tests_passed: row.tests_passed ?? null,
  };
}

async function gateway<T>(path: string): Promise<FetchResult<T>> {
  try {
    const r = await fetch(`${baseUrl()}${path}`, {
      headers: { Authorization: authHeader() },
      cache: "no-store",
    });
    const body = await r.json().catch(() => null);
    if (!r.ok) {
      return {
        ok: false,
        status: r.status,
        data: null,
        error: errorMessage(r.status, r.statusText, body),
      };
    }
    return { ok: true, status: r.status, data: body as T, error: null };
  } catch (e) {
    return {
      ok: false,
      status: 0,
      data: null,
      error: e instanceof Error ? e.message : "fetch failed",
    };
  }
}

export async function getOverview(range: Range): Promise<FetchResult<Overview>> {
  const r = await gateway<Overview>(`/v1/console/overview?range=${range}`);
  return { ...r, data: coerceOverview(r.data, range) };
}

export async function getInferences(
  range: Range,
  q = "",
  model = "",
): Promise<FetchResult<Inferences>> {
  const qs = new URLSearchParams({ range });
  if (q) qs.set("q", q);
  if (model) qs.set("model", model);
  const r = await gateway<Inferences>(`/v1/console/inferences?${qs}`);
  const rows = Array.isArray(r.data?.data) ? r.data.data.map(coerceInference) : [];
  return { ...r, data: { data: rows } };
}

export async function getModels(): Promise<FetchResult<ModelsResponse>> {
  const r = await gateway<ModelsResponse>("/v1/models");
  if (!r.ok || !r.data) {
    return { ...r, data: { object: "list", data: [] } };
  }
  return r;
}

export async function getHealth(): Promise<FetchResult<Health>> {
  const r = await gateway<Health>("/health");
  if (!r.ok || !r.data) {
    return { ...r, data: EMPTY_HEALTH };
  }
  return r;
}

function aiandOrigin(): string {
  return (process.env.AIAND_BASE_URL || "https://api.aiand.com/v1").replace(/\/v1\/?$/, "");
}

function scrub(text: string): string {
  const key = process.env.DATA_AIAND_API_KEY || "";
  return key ? text.split(key).join("[redacted]") : text;
}

async function aiand<T>(path: string): Promise<FetchResult<T>> {
  const key = process.env.DATA_AIAND_API_KEY || "";
  if (!key) {
    return { ok: false, status: 0, data: null, error: "DATA_AIAND_API_KEY is not set" };
  }
  try {
    const r = await fetch(`${aiandOrigin()}${path}`, {
      headers: { Authorization: `Bearer ${key}` },
      cache: "no-store",
    });
    const body = await r.json().catch(() => null);
    if (!r.ok) {
      return {
        ok: false,
        status: r.status,
        data: null,
        error: scrub(errorMessage(r.status, r.statusText, body)),
      };
    }
    return { ok: true, status: r.status, data: body as T, error: null };
  } catch (e) {
    return {
      ok: false,
      status: 0,
      data: null,
      error: e instanceof Error ? e.message : "fetch failed",
    };
  }
}

type LogsPage = {
  data?: unknown[];
  has_more?: boolean;
  next_after?: string;
  next_after_id?: string;
};

async function fetchLogPages(range: string, pages = 2): Promise<unknown[]> {
  const rows: unknown[] = [];
  let after = "";
  let afterId = "";
  for (let i = 0; i < pages; i++) {
    const qs = new URLSearchParams({ range, limit: "100" });
    if (after) qs.set("after", after);
    if (afterId) qs.set("after_id", afterId);
    const r = await aiand<LogsPage>(`/logs?${qs}`);
    if (!r.ok || !r.data) break;
    const chunk = Array.isArray(r.data.data) ? r.data.data : [];
    rows.push(...chunk);
    if (!r.data.has_more) break;
    after = r.data.next_after || "";
    afterId = r.data.next_after_id || "";
    if (!after && !afterId) break;
  }
  return rows;
}

export async function getUpstream(kind: "summary" | "metrics" | "logs", range: Range) {
  const mapped = toAiandRange(range);
  if (kind === "logs") return aiand<unknown>(`/logs?range=${mapped}&limit=100`);
  return aiand<unknown>(`/analytics/${kind}?range=${mapped}`);
}

export async function getOrgUsage(
  range: Range,
  q = "",
  model = "",
): Promise<FetchResult<OrgBundle>> {
  const mapped = toAiandRange(range);
  const [summaryRes, metricsRes, modelsRes, errorRes] = await Promise.all([
    aiand<unknown>(`/analytics/summary?range=${mapped}`),
    aiand<unknown>(`/analytics/metrics?range=${mapped}`),
    getModels(),
    aiand<LogsPage>(`/logs?range=${mapped}&errors=true&limit=50`),
  ]);
  if (!summaryRes.ok && !metricsRes.ok) {
    return {
      ok: false,
      status: summaryRes.status || metricsRes.status,
      data: null,
      error: summaryRes.error || metricsRes.error || "AIand analytics unavailable",
    };
  }
  const logs = await fetchLogPages(mapped);
  const catalog = (modelsRes.data?.data || [])
    .filter((m) => m.id !== "router/auto")
    .map((m) => ({
      id: m.id,
      display_name: m.display_name || m.id,
      enabled: m.enabled !== false,
    }));
  const overview = overlayOverview({
    range,
    summary: summaryRes.data,
    metrics: metricsRes.data,
    logs,
    catalog,
  });
  const needle = q.trim().toLowerCase();
  const inferences = parseLogs(logs)
    .map(logToInference)
    .filter((row) => {
      if (model && row.selected !== model) return false;
      if (!needle) return true;
      return `${row.selected || ""} ${row.path}`.toLowerCase().includes(needle);
    });
  const errors = parseLogs(errorRes.data).map(logToInference);
  return {
    ok: true,
    status: 200,
    data: { overview, inferences, errors },
    error: summaryRes.ok ? null : summaryRes.error,
  };
}

export function maskKey(): MaskedKey {
  const key = process.env.ROUTER_API_KEY || "";
  if (!key) {
    return { set: false, masked: "not set", hidden: "••••••••••••••••••••••••••" };
  }
  const prefix = key.slice(0, Math.min(8, key.length));
  return {
    set: true,
    masked: `${prefix}••••••••••••••••••`,
    hidden: "••••••••••••••••••••••••••",
  };
}

export function catalogCount(models: ModelsResponse | null): number {
  return (models?.data ?? []).filter((m) => m.id !== "router/auto").length;
}
