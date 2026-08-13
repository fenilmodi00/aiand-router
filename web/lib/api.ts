import "server-only";

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

export async function getUpstream(kind: "summary" | "metrics" | "logs", range: Range) {
  const mapped = toAiandRange(range);
  const path =
    kind === "logs"
      ? `/v1/console/upstream/logs?range=${mapped}`
      : `/v1/console/upstream/${kind}?range=${mapped}`;
  return gateway<unknown>(path);
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
