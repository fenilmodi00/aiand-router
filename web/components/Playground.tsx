"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { colorFor } from "@/lib/format";
import { MIX_COLORS, type CatalogModel } from "@/lib/types";

const EFFORTS = [
  { id: "low", hint: "Cheap-first" },
  { id: "medium", hint: "Balanced" },
  { id: "high", hint: "Prefer quality" },
  { id: "max", hint: "Best model every time" },
] as const;

const DEFAULT_SYSTEM =
  "You are an expert software engineer. Write clean, well-documented code with error handling.";
const DEFAULT_QUERY =
  "Write a Python function that implements binary search on a sorted list. Include type hints, a docstring, and handle the empty-list case.";

type Tab = "code" | "output" | "overview";

type Usage = { prompt: number; completion: number; total: number };

type Hop = {
  ok: boolean;
  status: number;
  headers: Record<string, string>;
  text: string;
  json: unknown;
  error?: string;
  e2eMs: number;
  ttftMs: number | null;
  finishReason: string;
  usage: Usage | null;
  inferenceId: string;
  system: string;
  query: string;
  effort: string;
  stream: boolean;
  jsonMode: boolean;
  allowed: string[];
};

function hdr(headers: Record<string, string>, name: string): string {
  return headers[name.toLowerCase()] || "";
}

function money(n: number): string {
  if (!Number.isFinite(n)) return "—";
  const s = n.toFixed(4).replace(/0+$/, "").replace(/\.$/, "");
  return `$${s}`;
}

function hopCost(m: CatalogModel | undefined, prompt: number, completion: number): number | null {
  if (!m || m.input_per_1m == null || m.output_per_1m == null) return null;
  return (prompt / 1_000_000) * m.input_per_1m + (completion / 1_000_000) * m.output_per_1m;
}

function priceLabel(n: number | undefined): string | null {
  if (n == null || !Number.isFinite(n)) return null;
  return `$${n.toFixed(2)}/1M`;
}

function displayName(m: CatalogModel | undefined, fallback: string): string {
  return m?.display_name || fallback;
}

function byId(models: CatalogModel[], id: string): CatalogModel | undefined {
  return models.find((m) => m.id === id);
}

function confidenceNum(raw: string): number | null {
  const n = Number(raw);
  return Number.isFinite(n) ? n : null;
}

function asPct(n: number): string {
  return `${(n <= 1 ? n * 100 : n).toFixed(1)}%`;
}

function asConf(n: number): string {
  return (n <= 1 ? n : n / 100).toFixed(3);
}

function usageFrom(json: unknown): Usage | null {
  if (!json || typeof json !== "object") return null;
  const u = (json as { usage?: { prompt_tokens?: number; completion_tokens?: number; total_tokens?: number } }).usage;
  if (!u) return null;
  const prompt = Number(u.prompt_tokens || 0);
  const completion = Number(u.completion_tokens || 0);
  return { prompt, completion, total: Number(u.total_tokens || prompt + completion) };
}

function finishFrom(json: unknown): string {
  if (!json || typeof json !== "object") return "";
  const fr = (json as { choices?: { finish_reason?: string }[] }).choices?.[0]?.finish_reason;
  return typeof fr === "string" ? fr : "";
}

function inferenceIdFrom(json: unknown): string {
  if (!json || typeof json !== "object") return "";
  const id = (json as { id?: unknown }).id;
  return typeof id === "string" ? id : "";
}

function replyText(json: unknown): string {
  if (!json || typeof json !== "object") return json == null ? "" : JSON.stringify(json, null, 2);
  const content = (json as { choices?: { message?: { content?: unknown } }[] }).choices?.[0]?.message?.content;
  if (typeof content === "string") return content;
  return JSON.stringify(json, null, 2);
}

function parseScore(reason: string): number | null {
  const m = reason.match(/score=([0-9.]+)/);
  if (!m) return null;
  const n = Number(m[1]);
  return Number.isFinite(n) ? n : null;
}

async function readSse(
  res: Response,
  onDelta: (text: string) => void,
): Promise<{ text: string; finish: string; usage: Usage | null; json: unknown; inferenceId: string }> {
  const reader = res.body?.getReader();
  if (!reader) return { text: "", finish: "", usage: null, json: null, inferenceId: "" };
  const dec = new TextDecoder();
  let buf = "";
  let text = "";
  let finish = "";
  let usage: Usage | null = null;
  let last: unknown = null;
  let inferenceId = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    const lines = buf.split("\n");
    buf = lines.pop() || "";
    for (const line of lines) {
      const t = line.trim();
      if (!t.startsWith("data:")) continue;
      const payload = t.slice(5).trim();
      if (!payload || payload === "[DONE]") continue;
      try {
        const obj = JSON.parse(payload) as {
          id?: string;
          usage?: Usage | { prompt_tokens?: number; completion_tokens?: number; total_tokens?: number };
          choices?: { delta?: { content?: string }; message?: { content?: string }; finish_reason?: string }[];
        };
        last = obj;
        if (typeof obj.id === "string") inferenceId = obj.id;
        const delta = obj.choices?.[0]?.delta?.content;
        if (typeof delta === "string") {
          text += delta;
          onDelta(text);
        }
        const msg = obj.choices?.[0]?.message?.content;
        if (typeof msg === "string") {
          text = msg;
          onDelta(text);
        }
        const fr = obj.choices?.[0]?.finish_reason;
        if (fr) finish = fr;
        if (obj.usage) usage = usageFrom({ usage: obj.usage });
      } catch {
        /* ignore malformed SSE lines */
      }
    }
  }
  return { text, finish, usage, json: last, inferenceId };
}

function requestPayload(p: {
  system: string;
  query: string;
  effort: string;
  stream: boolean;
  jsonMode: boolean;
  allowed: string[];
}) {
  const messages: { role: string; content: string }[] = [];
  if (p.system.trim()) messages.push({ role: "system", content: p.system.trim() });
  messages.push({ role: "user", content: p.query.trim() });
  const body: Record<string, unknown> = { model: "router/auto", messages, stream: p.stream };
  if (p.jsonMode) body.response_format = { type: "json_object" };
  return body;
}

function curlFor(p: {
  system: string;
  query: string;
  effort: string;
  stream: boolean;
  jsonMode: boolean;
  allowed: string[];
}): string {
  const body = JSON.stringify(requestPayload(p), null, 2);
  const headers = [
    `-H "Content-Type: application/json"`,
    `-H "Authorization: Bearer $ROUTER_API_KEY"`,
    `-H "x-routing-effort: ${p.effort}"`,
  ];
  if (p.allowed.length) headers.push(`-H "x-allowed-models: ${p.allowed.join(",")}"`);
  return `curl -X POST "$ROUTER_BASE_URL/v1/chat/completions" \\\n  ${headers.join(" \\\n  ")} \\\n  -d '${body.replace(/'/g, `'\\''`)}'`;
}

export function Playground({ models, loadError }: { models: CatalogModel[]; loadError?: string | null }) {
  const candidates = models;
  const [system, setSystem] = useState(DEFAULT_SYSTEM);
  const [query, setQuery] = useState(DEFAULT_QUERY);
  const [effort, setEffort] = useState<(typeof EFFORTS)[number]["id"]>("medium");
  const [stream, setStream] = useState(false);
  const [jsonMode, setJsonMode] = useState(false);
  const [checked, setChecked] = useState<Set<string>>(
    () => new Set(candidates.filter((m) => m.enabled !== false).map((m) => m.id)),
  );
  const [busy, setBusy] = useState(false);
  const [tab, setTab] = useState<Tab>("overview");
  const [hop, setHop] = useState<Hop | null>(null);
  const [liveText, setLiveText] = useState("");

  const allowed = useMemo(
    () => candidates.filter((m) => checked.has(m.id)).map((m) => m.id),
    [candidates, checked],
  );
  const effortMeta = EFFORTS.find((e) => e.id === effort) || EFFORTS[1];
  const req = { system, query, effort, stream, jsonMode, allowed };
  const codeSrc = hop
    ? { system: hop.system, query: hop.query, effort: hop.effort, stream: hop.stream, jsonMode: hop.jsonMode, allowed: hop.allowed }
    : req;

  function toggle(id: string) {
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function run() {
    if (busy || !query.trim() || allowed.length === 0) return;
    setBusy(true);
    setLiveText("");
    setTab("output");
    const t0 = performance.now();
    let ttft: number | null = null;
    const snapshot = { system, query, effort, stream, jsonMode, allowed: [...allowed] };
    try {
      const r = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt: query,
          system,
          effort,
          allowedModels: allowed,
          stream,
          jsonMode,
        }),
      });
      const ctype = r.headers.get("content-type") || "";
      if (ctype.includes("text/event-stream")) {
        const headers: Record<string, string> = {};
        r.headers.forEach((v, k) => {
          if (k.toLowerCase().startsWith("x-router-")) headers[k.toLowerCase()] = v;
        });
        const sse = await readSse(r, (text) => {
          if (ttft == null) ttft = performance.now() - t0;
          setLiveText(text);
        });
        setHop({
          ok: r.ok,
          status: r.status,
          headers,
          text: sse.text,
          json: sse.json,
          error: r.ok ? undefined : "stream error",
          e2eMs: performance.now() - t0,
          ttftMs: ttft,
          finishReason: sse.finish,
          usage: sse.usage,
          inferenceId: sse.inferenceId,
          ...snapshot,
        });
      } else {
        const data = (await r.json()) as {
          ok: boolean;
          status: number;
          headers: Record<string, string>;
          json: unknown;
          error?: string;
        };
        const headers: Record<string, string> = {};
        for (const [k, v] of Object.entries(data.headers || {})) headers[k.toLowerCase()] = v;
        setHop({
          ok: data.ok,
          status: data.status,
          headers,
          text: data.error && !data.json ? data.error : replyText(data.json),
          json: data.json,
          error: data.error,
          e2eMs: performance.now() - t0,
          ttftMs: null,
          finishReason: finishFrom(data.json),
          usage: usageFrom(data.json),
          inferenceId: inferenceIdFrom(data.json),
          ...snapshot,
        });
      }
    } catch (e) {
      setHop({
        ok: false,
        status: 0,
        headers: {},
        text: "",
        json: null,
        error: e instanceof Error ? e.message : "request failed",
        e2eMs: performance.now() - t0,
        ttftMs: ttft,
        finishReason: "",
        usage: null,
        inferenceId: "",
        ...snapshot,
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="pg-workspace">
      <div className="pg-left">
        <div className="pg-brand">
          <div className="pg-brand-id">
            router/auto
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M6 9l6 6 6-6" />
            </svg>
          </div>
          <div className="pg-brand-sub">Routes to the best-performing model</div>
        </div>

        <label className="pg-label">
          System prompt
          <textarea value={system} onChange={(e) => setSystem(e.target.value)} rows={3} />
        </label>

        <label className="pg-label">
          Query
          <div className="pg-query">
            <textarea
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              rows={6}
              onKeyDown={(e) => {
                if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
                  e.preventDefault();
                  void run();
                }
              }}
            />
            <button
              className="pg-run"
              type="button"
              disabled={busy || !query.trim() || allowed.length === 0}
              onClick={() => void run()}
            >
              {busy ? "Running…" : "Run →"}
            </button>
          </div>
        </label>

        <div className="pg-effort">
          <div className="pg-effort-head">
            <span>Routing effort</span>
            <span className="pg-effort-tip">
              {effortMeta.id} — {effortMeta.hint}
            </span>
          </div>
          <div className="pg-effort-row">
            <span className="pg-effort-end">Faster</span>
            <input
              type="range"
              min={0}
              max={EFFORTS.length - 1}
              step={1}
              value={EFFORTS.findIndex((e) => e.id === effort)}
              onChange={(e) => setEffort(EFFORTS[Number(e.target.value)]!.id)}
              aria-label="Routing effort"
            />
            <span className="pg-effort-end">Smarter</span>
          </div>
          <div className="pg-effort-ticks">
            {EFFORTS.map((e) => (
              <button
                key={e.id}
                type="button"
                className={e.id === effort ? "on" : ""}
                onClick={() => setEffort(e.id)}
              >
                {e.id}
              </button>
            ))}
          </div>
        </div>

        <div className="pg-cands">
          <div className="pg-cands-head">
            {allowed.length} of {candidates.length} enabled
          </div>
          {loadError ? <div className="pg-note">Could not load /v1/models ({loadError}).</div> : null}
          <div className="pg-cands-list">
            {candidates.map((m, i) => (
              <label key={m.id} className="pg-cand">
                <input type="checkbox" checked={checked.has(m.id)} onChange={() => toggle(m.id)} />
                <span className="pg-cand-dot" style={{ background: colorFor(m.id, i, MIX_COLORS) }} />
                <span className="pg-cand-name">{displayName(m, m.id)}</span>
                {priceLabel(m.input_per_1m) ? <span className="pg-cand-price">{priceLabel(m.input_per_1m)}</span> : null}
              </label>
            ))}
          </div>
          <p className="pg-caption">
            Effort and candidate models apply to this request only. Edit the saved policy on the{" "}
            <Link href="/routers/auto">router&apos;s settings page</Link>.
          </p>
        </div>

        <div className="pg-toggles">
          <label className="pg-toggle">
            <span>Output Schema</span>
            <input type="checkbox" role="switch" checked={jsonMode} onChange={(e) => setJsonMode(e.target.checked)} />
          </label>
          <label className="pg-toggle">
            <span>Stream response</span>
            <input type="checkbox" role="switch" checked={stream} onChange={(e) => setStream(e.target.checked)} />
          </label>
        </div>
      </div>

      <div className="pg-right">
        <div className="pg-tabs" role="tablist">
          <button type="button" role="tab" aria-selected={tab === "code"} className={tab === "code" ? "on" : ""} onClick={() => setTab("code")}>
            <span className="pg-tab-ico">&gt;_</span> Code
          </button>
          <button type="button" role="tab" aria-selected={tab === "output"} className={tab === "output" ? "on" : ""} onClick={() => setTab("output")}>
            <span className="pg-tab-ico">▷</span> Output
          </button>
          <button type="button" role="tab" aria-selected={tab === "overview"} className={tab === "overview" ? "on" : ""} onClick={() => setTab("overview")}>
            Overview
          </button>
        </div>
        <div className="pg-pane">
          {tab === "code" ? (
            <>
              <pre className="pg-out">{curlFor(codeSrc)}</pre>
              <pre className="pg-out" style={{ marginTop: 20, opacity: 0.9 }}>
                {JSON.stringify(requestPayload(codeSrc), null, 2)}
              </pre>
            </>
          ) : null}
          {tab === "output" ? (
            !hop && !busy ? (
              <div className="empty pg-empty">No hop yet.</div>
            ) : (
              <pre className="pg-out">
                {busy
                  ? liveText || (stream ? "Waiting for tokens…" : "Routing…")
                  : hop?.error && !hop.text
                    ? hop.error
                    : hop?.text}
              </pre>
            )
          ) : null}
          {tab === "overview" ? <OverviewPane hop={busy ? null : hop} models={candidates} /> : null}
        </div>
      </div>
    </div>
  );
}

function OverviewPane({ hop, models }: { hop: Hop | null; models: CatalogModel[] }) {
  if (!hop) {
    return <div className="empty pg-empty">No hop yet.</div>;
  }

  const modelId = hdr(hop.headers, "x-router-model");
  const path = hdr(hop.headers, "x-router-path");
  const phase = hdr(hop.headers, "x-router-phase");
  const threshold = hdr(hop.headers, "x-router-threshold");
  const rule = hdr(hop.headers, "x-router-rule");
  const reason = hdr(hop.headers, "x-router-reason");
  const conf = confidenceNum(hdr(hop.headers, "x-router-confidence"));
  const score = parseScore(reason);
  const savingsRaw = hdr(hop.headers, "x-router-savings-usd");
  const savingsHdr = savingsRaw === "" ? null : Number(savingsRaw);
  const baselineId = hdr(hop.headers, "x-router-baseline-model");
  const candIds = hdr(hop.headers, "x-router-candidates")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  const codes = hdr(hop.headers, "x-router-reason-codes")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  const chosen = byId(models, modelId);
  const prompt = hop.usage?.prompt ?? 0;
  const completion = hop.usage?.completion ?? 0;
  const hasUsage = hop.usage != null;
  const actual = hasUsage ? hopCost(chosen, prompt, completion) : null;
  const baselineModel = byId(models, baselineId);
  let baselineCost = hasUsage ? hopCost(baselineModel, prompt, completion) : null;
  if (baselineCost == null && hasUsage && candIds.length) {
    let max = -1;
    for (const id of candIds) {
      const c = hopCost(byId(models, id), prompt, completion);
      if (c != null && c > max) max = c;
    }
    if (max >= 0) baselineCost = max;
  }
  const savings =
    savingsHdr != null && Number.isFinite(savingsHdr)
      ? savingsHdr
      : actual != null && baselineCost != null
        ? Math.max(0, baselineCost - actual)
        : null;
  if (baselineCost == null && actual != null && savings != null) baselineCost = actual + savings;
  const savingsPct = savings != null && baselineCost && baselineCost > 0 ? (savings / baselineCost) * 100 : null;
  const pills = [...codes];
  if (path && !pills.includes(path)) pills.unshift(path);
  if (rule && !pills.includes(rule)) pills.push(rule);

  return (
    <div className="pg-overview">
      <div className="pg-pick">
        <div className="pg-pick-name">{displayName(chosen, modelId || "—")}</div>
        <div className="pg-pick-via">via router/auto{path ? ` · ${path}` : ""}</div>
        <div className={hop.ok ? "pg-ok" : "pg-bad"}>{hop.ok ? "✓ Success" : `HTTP ${hop.status}${hop.error ? ` · ${hop.error}` : ""}`}</div>
      </div>

      <div className="pg-kv">
        <span className="k">End-to-end latency</span>
        <span className="v">{(hop.e2eMs / 1000).toFixed(3)}s</span>
      </div>
      <div className="pg-kv">
        <span className="k">TTFT</span>
        <span className="v">{hop.ttftMs == null ? "—" : `${(hop.ttftMs / 1000).toFixed(3)}s`}</span>
      </div>
      <div className="pg-kv">
        <span className="k">Finish reason</span>
        <span className="v">{hop.finishReason || "—"}</span>
      </div>
      <div className="pg-kv">
        <span className="k">Phase</span>
        <span className="v">{phase || "—"}</span>
      </div>
      <div className="pg-kv">
        <span className="k">Routing rule</span>
        <span className="v">{rule || (reason ? reason.split(";")[0] : "—")}</span>
      </div>
      <div className="pg-kv">
        <span className="k">Confidence</span>
        <span className="v">{conf != null ? asPct(conf) : "—"}</span>
      </div>

      <div className="pg-kv">
        <span className="k">Input tokens</span>
        <span className="v">{hop.usage ? hop.usage.prompt.toLocaleString() : "—"}</span>
      </div>
      <div className="pg-kv">
        <span className="k">Output tokens</span>
        <span className="v">{hop.usage ? hop.usage.completion.toLocaleString() : "—"}</span>
      </div>
      <div className="pg-kv">
        <span className="k">Total tokens</span>
        <span className="v">{hop.usage ? hop.usage.total.toLocaleString() : "—"}</span>
      </div>

      <div className="pg-kv">
        <span className="k">Savings</span>
        <span className="v green">
          {savings == null ? "—" : `${money(savings)}${savingsPct != null ? ` (${Math.round(savingsPct)}%)` : ""}`}
        </span>
      </div>
      <div className="pg-kv">
        <span className="k">Most expensive option</span>
        <span className="v">{baselineCost == null ? "—" : money(baselineCost)}</span>
      </div>

      <div className="pg-kv">
        <span className="k">Model ID</span>
        <span className="v">{modelId || "—"}</span>
      </div>
      <div className="pg-kv">
        <span className="k">Provider</span>
        <span className="v">aiand-router</span>
      </div>
      <div className="pg-kv">
        <span className="k">Type</span>
        <span className="v">Router</span>
      </div>
      <div className="pg-kv">
        <span className="k">Threshold</span>
        <span className="v">{threshold || "—"}</span>
      </div>
      <div className="pg-kv">
        <span className="k">Inference ID</span>
        <span className="v">{hop.inferenceId || "—"}</span>
      </div>

      {hop.system ? (
        <div className="pg-sys">
          <div className="k">System prompt</div>
          <p>{hop.system}</p>
        </div>
      ) : null}

      <div className="pg-decision">
        <div className="pg-decision-title">Routing decision</div>
        <div className="pg-decision-grid">
          <div>
            <div className="k">Chosen model</div>
            <div className="v">{displayName(chosen, modelId || "—")}</div>
          </div>
          <div>
            <div className="k">Rule</div>
            <div className="v">{rule || "—"}</div>
          </div>
          <div>
            <div className="k">Confidence</div>
            <div className="v">{conf != null ? asConf(conf) : "—"}</div>
          </div>
          <div>
            <div className="k">Savings</div>
            <div className="v green">
              {savings == null ? "—" : `${money(savings)}${savingsPct != null ? ` / ${savingsPct.toFixed(1)}%` : ""}`}
            </div>
          </div>
        </div>
        {pills.length ? (
          <div className="pg-pills">
            {pills.map((p) => (
              <span key={p} className="pg-pill">
                {p}
              </span>
            ))}
          </div>
        ) : null}
        <table className="pg-cand-table">
          <thead>
            <tr>
              <th>Candidate</th>
              <th>Score</th>
              <th className="r">Est. cost</th>
            </tr>
          </thead>
          <tbody>
            {(candIds.length ? candIds : hop.allowed).map((id) => {
              const row = byId(models, id);
              const chosenRow = id === modelId;
              const cost = hasUsage ? hopCost(row, prompt, completion) : null;
              const rowScore = chosenRow ? (conf ?? score) : null;
              return (
                <tr key={id} className={chosenRow ? "chosen" : ""}>
                  <td>
                    {displayName(row, id)}
                    {chosenRow ? <span className="pg-chosen-tag">CHOSEN</span> : null}
                  </td>
                  <td>{rowScore != null ? asConf(rowScore) : "—"}</td>
                  <td className="r">{cost == null ? "—" : money(cost)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
