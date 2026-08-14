"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { ChevronDownIcon, PlayIcon, TerminalIcon } from "lucide-react";
import { colorFor } from "@/lib/format";
import { MIX_COLORS, type CatalogModel } from "@/lib/types";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field";
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupTextarea,
} from "@/components/ui/input-group";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Slider } from "@/components/ui/slider";
import { Spinner } from "@/components/ui/spinner";
import { Switch } from "@/components/ui/switch";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

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

  const effortIndex = EFFORTS.findIndex((e) => e.id === effort);

  return (
    <div className="grid min-h-[calc(100vh-140px)] overflow-hidden rounded-xl border bg-card lg:grid-cols-[minmax(320px,42%)_1fr]">
      <div className="flex flex-col gap-4 overflow-auto border-b p-[22px] lg:border-r lg:border-b-0">
        <div>
          <div className="inline-flex items-center gap-1.5 text-[15px] font-semibold">
            router/auto
            <ChevronDownIcon className="text-muted-foreground" />
          </div>
          <p className="mt-1 text-[12.5px] text-muted-foreground">Routes to the best-performing model</p>
        </div>

        <FieldGroup>
          <Field>
            <FieldLabel htmlFor="pg-system">System prompt</FieldLabel>
            <Textarea
              id="pg-system"
              value={system}
              onChange={(e) => setSystem(e.target.value)}
              rows={3}
              className="min-h-[72px] font-mono text-[13px]"
            />
          </Field>
          <Field>
            <FieldLabel htmlFor="pg-query">Query</FieldLabel>
            <InputGroup>
              <InputGroupTextarea
                id="pg-query"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                rows={6}
                className="min-h-[140px] font-mono text-[13px]"
                onKeyDown={(e) => {
                  if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
                    e.preventDefault();
                    void run();
                  }
                }}
              />
              <InputGroupAddon align="block-end" className="justify-end">
                <InputGroupButton
                  variant="default"
                  size="sm"
                  disabled={busy || !query.trim() || allowed.length === 0}
                  onClick={() => void run()}
                >
                  {busy ? <Spinner data-icon="inline-start" /> : <PlayIcon data-icon="inline-start" />}
                  {busy ? "Running…" : "Run"}
                </InputGroupButton>
              </InputGroupAddon>
            </InputGroup>
          </Field>
          <Field>
            <div className="flex items-baseline justify-between gap-3">
              <FieldLabel>Routing effort</FieldLabel>
              <FieldDescription className="font-mono text-[11.5px] text-success">
                {effortMeta.id} — {effortMeta.hint}
              </FieldDescription>
            </div>
            <div className="flex items-center gap-2.5">
              <span className="shrink-0 text-[11px] text-muted-foreground">Faster</span>
              <Slider
                min={0}
                max={EFFORTS.length - 1}
                step={1}
                value={effortIndex}
                onValueChange={(v) => {
                  const n = Array.isArray(v) ? v[0] : v;
                  if (n != null) setEffort(EFFORTS[n]!.id);
                }}
                aria-label="Routing effort"
              />
              <span className="shrink-0 text-[11px] text-muted-foreground">Smarter</span>
            </div>
            <div className="flex justify-between px-[42px]">
              {EFFORTS.map((e) => (
                <Button
                  key={e.id}
                  type="button"
                  variant="link"
                  size="sm"
                  className={cn("h-auto px-0 font-mono text-[11px]", e.id === effort ? "text-success" : "text-muted-foreground")}
                  onClick={() => setEffort(e.id)}
                >
                  {e.id}
                </Button>
              ))}
            </div>
          </Field>
        </FieldGroup>

        <div className="flex flex-col gap-2">
          <p className="text-xs text-muted-foreground">
            {allowed.length} of {candidates.length} enabled
          </p>
          {loadError ? (
            <Alert>
              <AlertTitle>Catalog error</AlertTitle>
              <AlertDescription>Could not load /v1/models ({loadError}).</AlertDescription>
            </Alert>
          ) : null}
          <ScrollArea className="h-[220px] rounded-lg border bg-muted">
            <div className="flex flex-col">
              {candidates.map((m, i) => (
                <label
                  key={m.id}
                  className="flex cursor-pointer items-center gap-2.5 border-b px-3 py-2 text-[13px] last:border-b-0"
                >
                  <Checkbox checked={checked.has(m.id)} onCheckedChange={() => toggle(m.id)} />
                  <span className="size-2 shrink-0 rounded-full" style={{ background: colorFor(m.id, i, MIX_COLORS) }} />
                  <span className="min-w-0 flex-1 truncate">{displayName(m, m.id)}</span>
                  {priceLabel(m.input_per_1m) ? (
                    <span className="shrink-0 font-mono text-xs text-muted-foreground">{priceLabel(m.input_per_1m)}</span>
                  ) : null}
                </label>
              ))}
            </div>
          </ScrollArea>
          <p className="text-xs leading-snug text-muted-foreground">
            Effort and candidate models apply to this request only. Edit the saved policy on the{" "}
            <Link href="/routers/auto" className="underline underline-offset-2 hover:text-foreground">
              router&apos;s settings page
            </Link>
            .
          </p>
        </div>

        <FieldGroup>
          <Field orientation="horizontal">
            <FieldLabel htmlFor="pg-json">Output Schema</FieldLabel>
            <Switch id="pg-json" checked={jsonMode} onCheckedChange={setJsonMode} />
          </Field>
          <Field orientation="horizontal">
            <FieldLabel htmlFor="pg-stream">Stream response</FieldLabel>
            <Switch id="pg-stream" checked={stream} onCheckedChange={setStream} />
          </Field>
        </FieldGroup>
      </div>

      <Tabs value={tab} onValueChange={(v) => setTab(v as Tab)} className="min-h-0 min-w-0 gap-0">
        <TabsList variant="line" className="w-full justify-start rounded-none border-b px-3.5 pt-2.5">
          <TabsTrigger value="code">
            <TerminalIcon data-icon="inline-start" />
            Code
          </TabsTrigger>
          <TabsTrigger value="output">
            <PlayIcon data-icon="inline-start" />
            Output
          </TabsTrigger>
          <TabsTrigger value="overview">Overview</TabsTrigger>
        </TabsList>
        <TabsContent value="code" className="overflow-auto p-[22px]">
          <pre className="font-mono text-[12.5px] leading-[1.6] whitespace-pre-wrap text-muted-foreground">
            {curlFor(codeSrc)}
          </pre>
          <pre className="mt-5 font-mono text-[12.5px] leading-[1.6] whitespace-pre-wrap text-muted-foreground opacity-90">
            {JSON.stringify(requestPayload(codeSrc), null, 2)}
          </pre>
        </TabsContent>
        <TabsContent value="output" className="overflow-auto p-[22px]">
          {!hop && !busy ? (
            <Empty className="min-h-[240px] border border-dashed">
              <EmptyHeader>
                <EmptyTitle>No hop yet</EmptyTitle>
                <EmptyDescription>Run a query to see the model output.</EmptyDescription>
              </EmptyHeader>
            </Empty>
          ) : (
            <pre className="font-mono text-[12.5px] leading-[1.6] whitespace-pre-wrap text-muted-foreground">
              {busy
                ? liveText || (stream ? "Waiting for tokens…" : "Routing…")
                : hop?.error && !hop.text
                  ? hop.error
                  : hop?.text}
            </pre>
          )}
        </TabsContent>
        <TabsContent value="overview" className="overflow-auto p-[22px]">
          <OverviewPane hop={busy ? null : hop} models={candidates} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function Kv({ k, v, green }: { k: string; v: string; green?: boolean }) {
  return (
    <div className="flex justify-between gap-4 border-b py-2.5 text-[13px]">
      <span className="text-muted-foreground">{k}</span>
      <span className={cn("text-right font-mono text-[12.5px] break-all", green && "text-success")}>{v}</span>
    </div>
  );
}

function OverviewPane({ hop, models }: { hop: Hop | null; models: CatalogModel[] }) {
  if (!hop) {
    return (
      <Empty className="min-h-[240px] border border-dashed">
        <EmptyHeader>
          <EmptyTitle>No hop yet</EmptyTitle>
          <EmptyDescription>Run a query to see routing details.</EmptyDescription>
        </EmptyHeader>
      </Empty>
    );
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
    <div className="max-w-[720px]">
      <div className="mb-1 border-b pb-4">
        <div className="text-lg font-semibold">{displayName(chosen, modelId || "—")}</div>
        <div className="mt-1 text-[13px] text-muted-foreground">
          via router/auto{path ? ` · ${path}` : ""}
        </div>
        <div className={cn("mt-2 text-[13px] font-medium", hop.ok ? "text-success" : "text-highlight")}>
          {hop.ok ? "✓ Success" : `HTTP ${hop.status}${hop.error ? ` · ${hop.error}` : ""}`}
        </div>
      </div>

      <Kv k="End-to-end latency" v={`${(hop.e2eMs / 1000).toFixed(3)}s`} />
      <Kv k="TTFT" v={hop.ttftMs == null ? "—" : `${(hop.ttftMs / 1000).toFixed(3)}s`} />
      <Kv k="Finish reason" v={hop.finishReason || "—"} />
      <Kv k="Phase" v={phase || "—"} />
      <Kv k="Routing rule" v={rule || (reason ? reason.split(";")[0] : "—")} />
      <Kv k="Confidence" v={conf != null ? asPct(conf) : "—"} />
      <Kv k="Input tokens" v={hop.usage ? hop.usage.prompt.toLocaleString() : "—"} />
      <Kv k="Output tokens" v={hop.usage ? hop.usage.completion.toLocaleString() : "—"} />
      <Kv k="Total tokens" v={hop.usage ? hop.usage.total.toLocaleString() : "—"} />
      <Kv
        k="Savings"
        v={savings == null ? "—" : `${money(savings)}${savingsPct != null ? ` (${Math.round(savingsPct)}%)` : ""}`}
        green
      />
      <Kv k="Most expensive option" v={baselineCost == null ? "—" : money(baselineCost)} />
      <Kv k="Model ID" v={modelId || "—"} />
      <Kv k="Provider" v="aiand-router" />
      <Kv k="Type" v="Router" />
      <Kv k="Threshold" v={threshold || "—"} />
      <Kv k="Inference ID" v={hop.inferenceId || "—"} />

      {hop.system ? (
        <div className="border-b py-3.5">
          <div className="text-[11px] font-medium tracking-[0.06em] text-muted-foreground uppercase">System prompt</div>
          <p className="mt-2 text-[13px] leading-normal text-muted-foreground">{hop.system}</p>
        </div>
      ) : null}

      <Card className="mt-[18px] gap-0 bg-muted py-0">
        <CardHeader className="pt-4 pb-0">
          <CardTitle className="text-[11px] font-medium tracking-[0.06em] text-muted-foreground uppercase">
            Routing decision
          </CardTitle>
        </CardHeader>
        <CardContent className="pb-2">
          <div className="my-3 grid grid-cols-2 gap-3 md:grid-cols-4">
            <div>
              <div className="text-[11px] font-medium tracking-[0.06em] text-muted-foreground uppercase">Chosen model</div>
              <div className="mt-1 text-[13px] font-medium">{displayName(chosen, modelId || "—")}</div>
            </div>
            <div>
              <div className="text-[11px] font-medium tracking-[0.06em] text-muted-foreground uppercase">Rule</div>
              <div className="mt-1 text-[13px] font-medium">{rule || "—"}</div>
            </div>
            <div>
              <div className="text-[11px] font-medium tracking-[0.06em] text-muted-foreground uppercase">Confidence</div>
              <div className="mt-1 text-[13px] font-medium">{conf != null ? asConf(conf) : "—"}</div>
            </div>
            <div>
              <div className="text-[11px] font-medium tracking-[0.06em] text-muted-foreground uppercase">Savings</div>
              <div className="mt-1 text-[13px] font-medium text-success">
                {savings == null ? "—" : `${money(savings)}${savingsPct != null ? ` / ${savingsPct.toFixed(1)}%` : ""}`}
              </div>
            </div>
          </div>
          {pills.length ? (
            <div className="mb-3 flex flex-wrap gap-1.5">
              {pills.map((p) => (
                <Badge key={p} variant="outline" className="font-mono text-[11px] font-normal">
                  {p}
                </Badge>
              ))}
            </div>
          ) : null}
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="text-[11px] tracking-[0.06em] uppercase">Candidate</TableHead>
                <TableHead className="text-[11px] tracking-[0.06em] uppercase">Score</TableHead>
                <TableHead className="text-right text-[11px] tracking-[0.06em] uppercase">Est. cost</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(candIds.length ? candIds : hop.allowed).map((id) => {
                const row = byId(models, id);
                const chosenRow = id === modelId;
                const cost = hasUsage ? hopCost(row, prompt, completion) : null;
                const rowScore = chosenRow ? (conf ?? score) : null;
                return (
                  <TableRow key={id} className={cn(chosenRow && "bg-highlight/15")}>
                    <TableCell>
                      {displayName(row, id)}
                      {chosenRow ? (
                        <Badge className="ml-2 bg-highlight text-[10px] font-bold tracking-wider text-accent-foreground">
                          CHOSEN
                        </Badge>
                      ) : null}
                    </TableCell>
                    <TableCell>{rowScore != null ? asConf(rowScore) : "—"}</TableCell>
                    <TableCell className="text-right">{cost == null ? "—" : money(cost)}</TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
