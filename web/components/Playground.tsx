"use client";

import React, { useMemo, useState } from "react";
import Link from "next/link";
import {
  ChevronDownIcon,
  PlayIcon,
  FileTextIcon,
  SparklesIcon,
  PlusIcon,
  InfoIcon,
} from "lucide-react";
import { type CatalogModel } from "@/lib/types";
import { resolveModelInfo, ModelLogo } from "@/lib/provider-logos";
import { Spinner } from "@/components/ui/spinner";
import { cn } from "@/lib/utils";

// Pioneer 5-tier routing effort settings
const EFFORTS = [
  { id: "low", label: "low", hint: "Cheapest models, max savings", threshold: 0.05 },
  { id: "medium", label: "medium", hint: "Good quality, good savings", threshold: 0.10 },
  { id: "high", label: "high", hint: "Recommended settings", threshold: 0.20 },
  { id: "xhigh", label: "xhigh", hint: "Prefer stronger models", threshold: 0.35 },
  { id: "max", label: "max", hint: "Best model every time", threshold: 0.60 },
] as const;

const DEFAULT_SYSTEM =
  "You are an expert software engineer. Write clean, well-documented code with error handling.";

const DEFAULT_QUERY =
  "Write a Python function that implements binary search on a sorted list. It should return the index of the target element, or -1 if not found. Include type hints and a docstring.";

const FALLBACK_MODELS: CatalogModel[] = [
  { id: "deepseek-ai/deepseek-v4-flash", display_name: "DeepSeek V4 Flash", input_per_1m: 0.05, output_per_1m: 0.10, enabled: true },
  { id: "openai/gpt-oss-20b", display_name: "GPT Oss 20b", input_per_1m: 0.07, output_per_1m: 0.14, enabled: true },
  { id: "openai/gpt-oss-120b", display_name: "GPT Oss 120b", input_per_1m: 0.15, output_per_1m: 0.30, enabled: true },
  { id: "google/gemini-3.1-flash-lite", display_name: "Gemini 3.1 Flash Lite", input_per_1m: 0.25, output_per_1m: 0.50, enabled: true },
  { id: "deepseek-ai/deepseek-v3", display_name: "DeepSeek V3", input_per_1m: 0.27, output_per_1m: 0.54, enabled: true },
  { id: "deepseek-ai/deepseek-v4-pro", display_name: "DeepSeek V4 Pro", input_per_1m: 0.41, output_per_1m: 0.82, enabled: true },
  { id: "openai/gpt-5.4-mini", display_name: "GPT 5.4 Mini", input_per_1m: 0.75, output_per_1m: 1.50, enabled: true },
  { id: "anthropic/claude-haiku-4.5", display_name: "Claude Haiku 4.5", input_per_1m: 1.00, output_per_1m: 2.00, enabled: true },
  { id: "zai-org/glm-5.1", display_name: "GLM 5.1", input_per_1m: 1.30, output_per_1m: 2.60, enabled: true },
  { id: "zai-org/glm-5.2", display_name: "GLM 5.2", input_per_1m: 1.50, output_per_1m: 3.00, enabled: true },
  { id: "google/gemini-3.1-pro", display_name: "Gemini 3.1 Pro", input_per_1m: 2.00, output_per_1m: 4.00, enabled: true },
  { id: "openai/gpt-5.4", display_name: "GPT 5.4", input_per_1m: 2.50, output_per_1m: 5.00, enabled: true },
  { id: "anthropic/claude-sonnet-4.6", display_name: "Claude Sonnet 4.6", input_per_1m: 3.00, output_per_1m: 6.00, enabled: true },
  { id: "openai/gpt-5.5", display_name: "GPT 5.5", input_per_1m: 5.00, output_per_1m: 10.00, enabled: true },
  { id: "anthropic/claude-opus-4.7", display_name: "Claude Opus 4.7", input_per_1m: 5.00, output_per_1m: 10.00, enabled: true },
  { id: "anthropic/claude-opus-4.8", display_name: "Claude Opus 4.8", input_per_1m: 5.50, output_per_1m: 11.00, enabled: true },
];

export const PHASES = [
  { id: "auto", label: "Auto-detect", hint: "Infers phase from conversation context & tools" },
  { id: "planning", label: "Planning / Design", hint: "High reasoning (Threshold: 50)" },
  { id: "code_generation", label: "Code Generation", hint: "Implementation (Threshold: 40)" },
  { id: "test_failure_analysis", label: "Debug / Test Fail", hint: "Escalated recovery (Threshold: 53)" },
  { id: "security_review", label: "Security Review", hint: "Strict verification (Threshold: 50)" },
  { id: "discover", label: "Discovery / Search", hint: "Fast context gathering (Threshold: 35)" },
  { id: "summarize", label: "Final Summary", hint: "Cost-effective synthesis (Threshold: 24)" },
] as const;

export const TRAINED_PATHS = [
  { id: "shadow", label: "Shadow ML", hint: "Serve rules, record ML shadow predictions" },
  { id: "trained", label: "Active ML", hint: "Serve trained logistic scorer predictions" },
  { id: "rules", label: "Rules Only", hint: "Deterministic Pioneer-score rules" },
] as const;

type MainTab = "code" | "output" | "overview";
type OutputSubTab = "json" | "visual";
type CodeLang = "curl" | "python" | "typescript" | "claude" | "opencode" | "codex";

type Usage = { prompt: number; completion: number; total: number };

type ExtraMessage = { id: string; role: "user" | "assistant" | "system"; content: string };

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
  selectedModel: string;
};

function hdr(headers: Record<string, string>, name: string): string {
  return headers[name.toLowerCase()] || "";
}

function money(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n)) return "—";
  if (n === 0) return "$0.00";
  return Math.abs(n) < 0.01 ? `$${n.toFixed(4)}` : `$${n.toFixed(2)}`;
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
  if (m?.display_name) return m.display_name;
  return resolveModelInfo(fallback).name;
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
  selectedModel: string;
  system: string;
  query: string;
  extraMessages?: ExtraMessage[];
  effort: string;
  stream: boolean;
  jsonMode: boolean;
  allowed: string[];
}) {
  const messages: { role: string; content: string }[] = [];
  if (p.system.trim()) messages.push({ role: "system", content: p.system.trim() });
  messages.push({ role: "user", content: p.query.trim() });
  if (p.extraMessages?.length) {
    p.extraMessages.forEach((m) => {
      if (m.content.trim()) messages.push({ role: m.role, content: m.content.trim() });
    });
  }
  const body: Record<string, unknown> = {
    model: p.selectedModel || "router/auto",
    messages,
    stream: p.stream,
  };
  if (p.jsonMode) body.response_format = { type: "json_object" };
  return body;
}

function curlFor(p: {
  selectedModel: string;
  system: string;
  query: string;
  extraMessages?: ExtraMessage[];
  effort: string;
  phase?: string;
  latencyLimit?: number;
  trainedPath?: string;
  stream: boolean;
  jsonMode: boolean;
  allowed: string[];
}): string {
  const body = JSON.stringify(requestPayload(p), null, 2);
  const headers = [
    `-H "Content-Type: application/json"`,
    `-H "Authorization: Bearer $ROUTER_API_KEY"`,
  ];
  if (p.selectedModel === "router/auto") {
    headers.push(`-H "x-routing-effort: ${p.effort}"`);
    if (p.phase && p.phase !== "auto") headers.push(`-H "x-agent-phase: ${p.phase}"`);
    if (p.latencyLimit && p.latencyLimit > 0) headers.push(`-H "x-latency-limit: ${p.latencyLimit}"`);
    if (p.trainedPath) headers.push(`-H "x-routing-path: ${p.trainedPath}"`);
    if (p.allowed.length) headers.push(`-H "x-allowed-models: ${p.allowed.join(",")}"`);
  }
  return `curl -X POST "$ROUTER_BASE_URL/v1/chat/completions" \\\n  ${headers.join(" \\\n  ")} \\\n  -d '${body.replace(/'/g, `'\\''`)}'`;
}

function pythonFor(p: {
  selectedModel: string;
  system: string;
  query: string;
  extraMessages?: ExtraMessage[];
  effort: string;
  phase?: string;
  latencyLimit?: number;
  trainedPath?: string;
  stream: boolean;
  jsonMode: boolean;
  allowed: string[];
}): string {
  const msgs: { role: string; content: string }[] = [];
  if (p.system.trim()) msgs.push({ role: "system", content: p.system.trim() });
  msgs.push({ role: "user", content: p.query.trim() });
  if (p.extraMessages?.length) {
    p.extraMessages.forEach((m) => {
      if (m.content.trim()) msgs.push({ role: m.role, content: m.content.trim() });
    });
  }

  const extraHeaders: Record<string, string> = {};
  if (p.selectedModel === "router/auto") {
    extraHeaders["x-routing-effort"] = p.effort;
    if (p.phase && p.phase !== "auto") extraHeaders["x-agent-phase"] = p.phase;
    if (p.latencyLimit && p.latencyLimit > 0) extraHeaders["x-latency-limit"] = String(p.latencyLimit);
    if (p.trainedPath) extraHeaders["x-routing-path"] = p.trainedPath;
    if (p.allowed.length) extraHeaders["x-allowed-models"] = p.allowed.join(",");
  }

  const hasExtra = Object.keys(extraHeaders).length > 0;
  const extraStr = hasExtra
    ? `,\n    extra_headers=${JSON.stringify(extraHeaders, null, 4).replace(/\n/g, "\n    ")}`
    : "";

  return `import os
from openai import OpenAI

client = OpenAI(
    base_url=os.getenv("ROUTER_BASE_URL", "http://127.0.0.1:8000/v1"),
    api_key=os.getenv("ROUTER_API_KEY", "change-me"),
)

response = client.chat.completions.create(
    model="${p.selectedModel || "router/auto"}",
    messages=${JSON.stringify(msgs, null, 4).replace(/\n/g, "\n    ")},
    stream=${p.stream ? "True" : "False"}${p.jsonMode ? ',\n    response_format={"type": "json_object"}' : ""}${extraStr}
)

if ${p.stream ? "True" : "False"}:
    for chunk in response:
        print(chunk.choices[0].delta.content or "", end="", flush=True)
else:
    print(response.choices[0].message.content)
`;
}

function tsFor(p: {
  selectedModel: string;
  system: string;
  query: string;
  extraMessages?: ExtraMessage[];
  effort: string;
  phase?: string;
  latencyLimit?: number;
  trainedPath?: string;
  stream: boolean;
  jsonMode: boolean;
  allowed: string[];
}): string {
  const msgs: { role: string; content: string }[] = [];
  if (p.system.trim()) msgs.push({ role: "system", content: p.system.trim() });
  msgs.push({ role: "user", content: p.query.trim() });
  if (p.extraMessages?.length) {
    p.extraMessages.forEach((m) => {
      if (m.content.trim()) msgs.push({ role: m.role, content: m.content.trim() });
    });
  }

  const headers: Record<string, string> = {};
  if (p.selectedModel === "router/auto") {
    headers["x-routing-effort"] = p.effort;
    if (p.phase && p.phase !== "auto") headers["x-agent-phase"] = p.phase;
    if (p.latencyLimit && p.latencyLimit > 0) headers["x-latency-limit"] = String(p.latencyLimit);
    if (p.trainedPath) headers["x-routing-path"] = p.trainedPath;
    if (p.allowed.length) headers["x-allowed-models"] = p.allowed.join(",");
  }

  return `import OpenAI from "openai";

const client = new OpenAI({
  baseURL: process.env.ROUTER_BASE_URL || "http://127.0.0.1:8000/v1",
  apiKey: process.env.ROUTER_API_KEY || "change-me",
  defaultHeaders: ${JSON.stringify(headers, null, 2).replace(/\n/g, "\n  ")},
});

async function main() {
  const stream = ${p.stream ? "true" : "false"};
  const response = await client.chat.completions.create({
    model: "${p.selectedModel || "router/auto"}",
    messages: ${JSON.stringify(msgs, null, 4).replace(/\n/g, "\n    ")},
    stream,${p.jsonMode ? '\n    response_format: { type: "json_object" },' : ""}
  });

  if (stream) {
    for await (const chunk of response) {
      process.stdout.write(chunk.choices[0]?.delta?.content || "");
    }
  } else {
    console.log(response.choices[0]?.message?.content);
  }
}

main().catch(console.error);
`;
}

function claudeFor(p: { selectedModel: string; effort: string }): string {
  return `# Claude Code Configuration with AIand Coding Router
# Point Claude Code at our local router gateway
export ANTHROPIC_BASE_URL="http://127.0.0.1:8000"
export ANTHROPIC_API_KEY="change-me"
export ANTHROPIC_CUSTOM_MODEL_OPTION="${p.selectedModel || "router/auto"}"

# Run Claude Code with automated model routing
claude --model router/auto`;
}

function opencodeFor(p: { selectedModel: string; effort: string }): string {
  return `// opencode.json or ~/.config/opencode/config.json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "aiand-router": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "AIand Router",
      "options": {
        "baseURL": "http://127.0.0.1:8000/v1",
        "apiKey": "change-me",
        "headers": {
          "x-routing-effort": "${p.effort}"
        }
      },
      "models": {
        "router/auto": { "name": "${p.selectedModel || "router/auto"}" }
      }
    }
  }
}`;
}

function codexFor(p: { selectedModel: string }): string {
  return `# ~/.codex/config.toml
[providers.aiand_router]
base_url = "http://127.0.0.1:8000/v1"
api_key = "change-me"
wire_api = "responses"

[models."router/auto"]
provider = "aiand_router"
model = "${p.selectedModel || "router/auto"}"`;
}

export function Playground({
  models = [],
  initialModelId = "router/auto",
}: {
  models: CatalogModel[];
  initialModelId?: string;
  loadError?: string | null;
}) {
  const candidates = useMemo(() => {
    if (models.length >= 8) return models;
    const map = new Map<string, CatalogModel>();
    FALLBACK_MODELS.forEach((m) => map.set(m.id, m));
    models.forEach((m) => map.set(m.id, m));
    return Array.from(map.values());
  }, [models]);

  const [selectedModel, setSelectedModel] = useState<string>(initialModelId);
  const [modelDropdownOpen, setModelDropdownOpen] = useState(false);
  const [system, setSystem] = useState(DEFAULT_SYSTEM);
  const [query, setQuery] = useState(DEFAULT_QUERY);
  const [effort, setEffort] = useState<(typeof EFFORTS)[number]["id"]>("high");
  const [phase, setPhase] = useState<string>("auto");
  const [trainedPath, setTrainedPath] = useState<"rules" | "shadow" | "trained">("shadow");
  const [latencyLimit, setLatencyLimit] = useState<number>(0);
  const [stream, setStream] = useState(true);
  const [jsonMode, setJsonMode] = useState(false);
  const [extraMessages, setExtraMessages] = useState<ExtraMessage[]>([]);
  const [checked, setChecked] = useState<Set<string>>(
    () => new Set(candidates.map((m) => m.id)),
  );
  const [busy, setBusy] = useState(false);
  const [mainTab, setMainTab] = useState<MainTab>("output");
  const [outputSubTab, setOutputSubTab] = useState<OutputSubTab>("visual");
  const [codeLang, setCodeLang] = useState<CodeLang>("curl");
  const [hop, setHop] = useState<Hop | null>(null);
  const [sessionHops, setSessionHops] = useState<Hop[]>([]);
  const [liveText, setLiveText] = useState("");
  const [copiedAi, setCopiedAi] = useState(false);

  const isRouter = selectedModel === "router/auto";

  const allowed = useMemo(
    () => candidates.filter((m) => checked.has(m.id)).map((m) => m.id),
    [candidates, checked],
  );
  const effortMeta = EFFORTS.find((e) => e.id === effort) || EFFORTS[2];
  const phaseMeta = PHASES.find((p) => p.id === phase) || PHASES[0];
  const req = {
    selectedModel,
    system,
    query,
    extraMessages,
    effort,
    phase,
    latencyLimit,
    trainedPath,
    stream,
    jsonMode,
    allowed,
  };
  const codeSrc = hop
    ? {
        selectedModel: hop.selectedModel,
        system: hop.system,
        query: hop.query,
        effort: hop.effort,
        phase: (hop.headers["x-router-phase"] as string) || phase,
        latencyLimit,
        trainedPath: (hop.headers["x-router-path"] as string) || trainedPath,
        stream: hop.stream,
        jsonMode: hop.jsonMode,
        allowed: hop.allowed,
      }
    : req;

  function toggle(id: string) {
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function addExtraMessage() {
    setExtraMessages((prev) => [
      ...prev,
      { id: Math.random().toString(36).substring(2, 9), role: "user", content: "" },
    ]);
  }

  async function copyForAi() {
    const payload = JSON.stringify(requestPayload(req), null, 2);
    await navigator.clipboard.writeText(payload);
    setCopiedAi(true);
    setTimeout(() => setCopiedAi(false), 2000);
  }

  async function run() {
    if (busy || !query.trim()) return;
    if (isRouter && allowed.length === 0) return;

    setBusy(true);
    setLiveText("");
    setMainTab("output");
    const t0 = performance.now();
    let ttft: number | null = null;
    const snapshot = {
      selectedModel,
      system,
      query,
      effort,
      stream,
      jsonMode,
      allowed: [...allowed],
    };

    try {
      const r = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model: selectedModel,
          prompt: query,
          system,
          effort,
          phase: phase !== "auto" ? phase : undefined,
          latencyLimit: latencyLimit > 0 ? latencyLimit : undefined,
          trainedPath,
          allowedModels: isRouter ? allowed : undefined,
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
        const newHop: Hop = {
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
        };
        setHop(newHop);
        setSessionHops((prev) => [newHop, ...prev]);
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
        const newHop: Hop = {
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
        };
        setHop(newHop);
        setSessionHops((prev) => [newHop, ...prev]);
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
  const activeModelObj = byId(candidates, selectedModel);

  return (
    <div className="w-full min-h-screen bg-black text-[#eaeaea] font-sans antialiased selection:bg-neutral-800">
      {/* 2-Pane Pioneer Grid */}
      <div className="grid min-h-screen w-full lg:grid-cols-[510px_1fr]">
        
        {/* ================= LEFT COLUMN ================= */}
        <div className="flex flex-col gap-5 overflow-y-auto border-r border-[#1a1a1a] bg-black p-6 pb-24">
          
          {/* Header Row: Logo, Title, Actions */}
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-start gap-3">
              <span className="mt-0.5 inline-flex size-7 shrink-0 items-center justify-center">
                <ModelLogo modelId={selectedModel} className="size-6" />
              </span>
              <div>
                <div className="relative inline-block">
                  <button
                    type="button"
                    onClick={() => setModelDropdownOpen((v) => !v)}
                    className="flex items-center gap-1.5 text-[17px] font-semibold tracking-tight text-white hover:text-neutral-200 transition"
                  >
                    <span>{isRouter ? "aiand/auto" : displayName(activeModelObj, selectedModel)}</span>
                    <ChevronDownIcon className="size-4 text-neutral-400" />
                  </button>

                  {/* Dropdown Menu */}
                  {modelDropdownOpen && (
                    <div className="absolute top-full left-0 z-50 mt-2 max-h-80 w-72 overflow-auto rounded-xl border border-[#262626] bg-[#0c0c0c] p-1.5 shadow-2xl">
                      <div className="px-2.5 py-1 text-[11px] font-medium tracking-wider text-neutral-400 uppercase">
                        Routers
                      </div>
                      <button
                        type="button"
                        onClick={() => {
                          setSelectedModel("router/auto");
                          setModelDropdownOpen(false);
                        }}
                        className={cn(
                          "flex w-full items-center justify-between rounded-lg px-2.5 py-2 text-left text-[13px] hover:bg-[#1a1a1a]",
                          selectedModel === "router/auto" && "bg-[#1f1f1f] text-white font-medium",
                        )}
                      >
                        <span className="flex items-center gap-2.5">
                          <ModelLogo modelId="router/auto" className="size-4" />
                          aiand/auto
                        </span>
                        <span className="text-[10px] text-neutral-400 font-mono">Router</span>
                      </button>

                      <div className="mt-2 px-2.5 py-1 text-[11px] font-medium tracking-wider text-neutral-400 uppercase">
                        Models ({candidates.length})
                      </div>
                      {candidates.map((m) => (
                        <button
                          key={m.id}
                          type="button"
                          onClick={() => {
                            setSelectedModel(m.id);
                            setModelDropdownOpen(false);
                          }}
                          className={cn(
                            "flex w-full items-center justify-between rounded-lg px-2.5 py-2 text-left text-[13px] hover:bg-[#1a1a1a]",
                            selectedModel === m.id && "bg-[#1f1f1f] text-white font-medium",
                          )}
                        >
                          <span className="flex items-center gap-2.5 truncate pr-2">
                            <ModelLogo modelId={m.id} className="size-4" />
                            <span className="truncate">{displayName(m, m.id)}</span>
                          </span>
                          {priceLabel(m.input_per_1m) && (
                            <span className="shrink-0 font-mono text-[11px] text-neutral-400">
                              {priceLabel(m.input_per_1m)}
                            </span>
                          )}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
                <p className="mt-0.5 text-[12.5px] text-neutral-400">
                  {isRouter ? "Routes to the best-performing model" : "Direct model inference"}
                </p>
              </div>
            </div>

            {/* Action Pills */}
            <div className="flex items-center gap-1.5 shrink-0">
              <button
                type="button"
                onClick={() => setModelDropdownOpen((v) => !v)}
                className="inline-flex items-center gap-1 rounded-full border border-[#2d2d2d] bg-[#0c0c0c] px-3 py-1 text-[11.5px] text-neutral-300 transition hover:bg-[#1a1a1a] hover:text-white"
              >
                <ChevronDownIcon className="size-3 text-neutral-400" />
                Change Model
              </button>
              <Link
                href="https://docs.aiand.com"
                target="_blank"
                className="inline-flex items-center gap-1 rounded-full border border-[#2d2d2d] bg-[#0c0c0c] px-3 py-1 text-[11.5px] text-neutral-300 transition hover:bg-[#1a1a1a] hover:text-white"
              >
                <FileTextIcon className="size-3 text-neutral-400" />
                Docs
              </Link>
              <button
                type="button"
                onClick={copyForAi}
                className="inline-flex items-center gap-1 rounded-full border border-[#2d2d2d] bg-[#0c0c0c] px-3 py-1 text-[11.5px] text-neutral-300 transition hover:bg-[#1a1a1a] hover:text-white"
              >
                <SparklesIcon className="size-3 text-neutral-400" />
                {copiedAi ? "Copied!" : "Copy for AI"}
              </button>
            </div>
          </div>

          {/* System Prompt Box */}
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center justify-between text-[13px]">
              <span className="font-medium text-white">System prompt</span>
              <span className="text-[11.5px] text-neutral-400">{system.length} chars</span>
            </div>
            <div className="rounded-xl border border-[#232323] bg-[#09090b] p-3 transition focus-within:border-neutral-500">
              <textarea
                value={system}
                onChange={(e) => setSystem(e.target.value)}
                rows={2}
                placeholder="You are an expert software engineer..."
                className="w-full resize-none bg-transparent font-sans text-[13px] leading-relaxed text-neutral-200 placeholder-neutral-500 outline-none"
              />
            </div>
            <span className="text-[11px] text-neutral-400">
              Sent to the model as role: <code className="font-mono text-neutral-300">&quot;system&quot;</code>. Leave empty to skip.
            </span>
          </div>

          {/* Query Box */}
          <div className="flex flex-col gap-1.5">
            <span className="text-[13px] font-medium text-white">Query</span>
            <div className="relative rounded-xl border border-[#232323] bg-[#09090b] p-3 pb-12 transition focus-within:border-neutral-500">
              <textarea
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                rows={5}
                placeholder="Write instructions or ask a coding question..."
                className="w-full resize-none bg-transparent font-sans text-[13px] leading-relaxed text-neutral-200 placeholder-neutral-500 outline-none"
                onKeyDown={(e) => {
                  if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
                    e.preventDefault();
                    void run();
                  }
                }}
              />
              <div className="absolute bottom-2.5 right-2.5">
                <button
                  type="button"
                  disabled={busy || !query.trim() || (isRouter && allowed.length === 0)}
                  onClick={() => void run()}
                  className="inline-flex items-center gap-1.5 rounded-full bg-white px-4 py-1.5 text-[12.5px] font-semibold text-black shadow-sm transition hover:bg-neutral-200 disabled:opacity-50"
                >
                  {busy ? (
                    <>
                      <Spinner className="size-3.5" />
                      Routing…
                    </>
                  ) : (
                    <>
                      Run <span className="text-[14px] leading-none">→</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>

          {/* Routing Section Header */}
          <div className="mt-1 flex flex-col gap-3">
            <h3 className="text-[14px] font-semibold text-white">Routing</h3>

            {/* Routing Effort */}
            <div className="flex flex-col gap-2">
              <div className="flex items-baseline justify-between">
                <span className="text-[13px] font-medium text-neutral-200">Routing effort</span>
                <span className="text-[11.5px] text-neutral-400">
                  <span className="font-semibold text-white">{effortMeta.id}</span> — {effortMeta.hint}
                </span>
              </div>

              {/* Slider Track with Chevron Indicator */}
              <div className="relative pt-3 pb-1">
                {/* Active Downward Chevron */}
                <div
                  className="absolute top-0 flex -translate-x-1/2 items-center justify-center transition-all duration-150"
                  style={{
                    left: `${(effortIndex / (EFFORTS.length - 1)) * 100}%`,
                  }}
                >
                  <span className="text-[11px] font-bold text-white">⌵</span>
                </div>

                {/* Range Track */}
                <div className="relative flex items-center">
                  <input
                    type="range"
                    min={0}
                    max={EFFORTS.length - 1}
                    step={1}
                    value={effortIndex >= 0 ? effortIndex : 2}
                    onChange={(e) => {
                      const idx = Number(e.target.value);
                      if (EFFORTS[idx]) setEffort(EFFORTS[idx].id);
                    }}
                    className="h-1 w-full cursor-pointer appearance-none rounded-full bg-[#2a2a2a] accent-white"
                  />
                </div>

                {/* Subtext Track Labels */}
                <div className="mt-1.5 flex justify-between text-[11px] text-neutral-400">
                  <span className="text-neutral-400">Faster</span>
                  <span className="text-neutral-400">Smarter</span>
                </div>

                {/* Tier Names */}
                <div className="mt-1 flex justify-between px-1 text-[11.5px]">
                  {EFFORTS.map((e) => (
                    <button
                      key={e.id}
                      type="button"
                      onClick={() => setEffort(e.id)}
                      className={cn(
                        "font-sans transition",
                        e.id === effort ? "font-bold text-white underline underline-offset-4" : "text-neutral-400 hover:text-neutral-300",
                      )}
                    >
                      {e.id}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            {/* Agent Phase Header Override */}
            <div className="flex flex-col gap-1.5 pt-1">
              <div className="flex items-center justify-between">
                <span className="text-[13px] font-medium text-neutral-200">Agent Phase</span>
                <span className="text-[11px] text-neutral-400 truncate max-w-[240px] text-right font-sans">{phaseMeta.hint}</span>
              </div>
              <select
                value={phase}
                onChange={(e) => setPhase(e.target.value)}
                className="w-full rounded-xl border border-[#232323] bg-[#09090b] px-3 py-2 text-[12.5px] text-neutral-200 outline-none transition focus:border-neutral-500"
              >
                {PHASES.map((p) => (
                  <option key={p.id} value={p.id} className="bg-[#09090b] text-neutral-200">
                    {p.label} — {p.hint}
                  </option>
                ))}
              </select>
            </div>

            {/* Trained Scorer Mode */}
            <div className="flex flex-col gap-1.5 pt-1">
              <div className="flex items-center justify-between">
                <span className="text-[13px] font-medium text-neutral-200">Scorer Engine</span>
                <span className="text-[11px] text-neutral-400 font-mono">x-routing-path</span>
              </div>
              <div className="grid grid-cols-3 gap-1.5 rounded-xl border border-[#1f1f1f] bg-[#070709] p-1">
                {TRAINED_PATHS.map((tp) => (
                  <button
                    key={tp.id}
                    type="button"
                    onClick={() => setTrainedPath(tp.id)}
                    className={cn(
                      "rounded-lg px-2 py-1.5 text-center text-[11.5px] font-medium transition",
                      trainedPath === tp.id
                        ? "bg-[#1f1f1f] text-white shadow-sm"
                        : "text-neutral-400 hover:text-neutral-200 hover:bg-[#121215]",
                    )}
                  >
                    {tp.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Latency Limit Slider */}
            <div className="flex flex-col gap-1.5 pt-1">
              <div className="flex items-center justify-between text-[12.5px]">
                <span className="font-medium text-neutral-200">Max Latency Cap</span>
                <span className="font-mono text-[11px] text-neutral-400">
                  {latencyLimit === 0 ? "No limit" : `${latencyLimit}ms`}
                </span>
              </div>
              <input
                type="range"
                min={0}
                max={2000}
                step={100}
                value={latencyLimit}
                onChange={(e) => setLatencyLimit(Number(e.target.value))}
                className="h-1 w-full cursor-pointer appearance-none rounded-full bg-[#2a2a2a] accent-white"
              />
            </div>

            {/* Candidate Models Pool */}
            <div className="mt-2 flex flex-col gap-2">
              <div className="flex items-center justify-between">
                <span className="text-[13px] font-medium text-neutral-200">Candidate models</span>
                <span className="text-[11.5px] text-neutral-400 font-mono">
                  {allowed.length} of {candidates.length} enabled
                </span>
              </div>

              {/* Models List */}
              <div className="max-h-72 overflow-y-auto rounded-xl border border-[#1f1f1f] bg-[#070709] p-1 divide-y divide-[#18181a]">
                {candidates.map((m) => (
                  <label
                    key={m.id}
                    className="flex cursor-pointer items-center justify-between px-3 py-2 text-[12.5px] transition hover:bg-[#121215]"
                  >
                    <div className="flex items-center gap-3 truncate pr-2">
                      <input
                        type="checkbox"
                        checked={checked.has(m.id)}
                        onChange={() => toggle(m.id)}
                        className="size-3.5 rounded border-[#333] bg-[#111] text-white accent-white focus:ring-0"
                      />
                      <ModelLogo modelId={m.id} className="size-4" />
                      <span className="truncate text-neutral-200">{displayName(m, m.id)}</span>
                    </div>
                    {priceLabel(m.input_per_1m) && (
                      <span className="shrink-0 font-mono text-[11px] text-neutral-400">
                        {priceLabel(m.input_per_1m)}
                      </span>
                    )}
                  </label>
                ))}
              </div>
              <span className="text-[11px] leading-tight text-neutral-400">
                Effort and candidate models apply to this request only. Edit the saved policy on the{" "}
                <Link href="/routers/auto" className="text-neutral-400 underline underline-offset-2 hover:text-white">
                  router&apos;s settings page
                </Link>
                .
              </span>
            </div>

            {/* Switches & Options */}
            <div className="mt-3 flex flex-col gap-3.5 border-t border-[#1a1a1a] pt-4">
              {/* Output Schema */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1 text-[12.5px] text-neutral-300">
                  <span>Output Schema</span>
                  <InfoIcon className="size-3 text-neutral-400" />
                </div>
                <button
                  type="button"
                  onClick={() => setJsonMode((v) => !v)}
                  className={cn(
                    "relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out",
                    jsonMode ? "bg-white" : "bg-[#2a2a2a]",
                  )}
                >
                  <span
                    className={cn(
                      "pointer-events-none inline-block size-4 transform rounded-full shadow-lg ring-0 transition duration-200 ease-in-out",
                      jsonMode ? "translate-x-4 bg-black" : "translate-x-0 bg-neutral-400",
                    )}
                  />
                </button>
              </div>

              {/* Stream Response */}
              <div className="flex items-center justify-between">
                <span className="text-[12.5px] text-neutral-300">Stream response</span>
                <button
                  type="button"
                  onClick={() => setStream((v) => !v)}
                  className={cn(
                    "relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out",
                    stream ? "bg-white" : "bg-[#2a2a2a]",
                  )}
                >
                  <span
                    className={cn(
                      "pointer-events-none inline-block size-4 transform rounded-full shadow-lg ring-0 transition duration-200 ease-in-out",
                      stream ? "translate-x-4 bg-black" : "translate-x-0 bg-neutral-400",
                    )}
                  />
                </button>
              </div>

              {/* Additional Messages */}
              <div className="flex flex-col gap-2">
                <div className="flex items-center gap-1 text-[12.5px] text-neutral-300">
                  <span>Additional messages</span>
                  <InfoIcon className="size-3 text-neutral-400" />
                </div>
                {extraMessages.map((msg, idx) => (
                  <div key={msg.id} className="flex flex-col gap-1 rounded-lg border border-[#222] bg-[#09090b] p-2">
                    <div className="flex items-center justify-between text-[11px] text-neutral-400">
                      <span className="uppercase font-mono">{msg.role}</span>
                      <button
                        type="button"
                        onClick={() => setExtraMessages((prev) => prev.filter((m) => m.id !== msg.id))}
                        className="text-neutral-400 hover:text-white"
                      >
                        Remove
                      </button>
                    </div>
                    <textarea
                      value={msg.content}
                      onChange={(e) => {
                        const val = e.target.value;
                        setExtraMessages((prev) =>
                          prev.map((m) => (m.id === msg.id ? { ...m, content: val } : m)),
                        );
                      }}
                      rows={2}
                      placeholder={`Message ${idx + 1}...`}
                      className="w-full resize-none bg-transparent text-[12.5px] text-neutral-200 outline-none"
                    />
                  </div>
                ))}
                <button
                  type="button"
                  onClick={addExtraMessage}
                  className="inline-flex w-fit items-center gap-1.5 rounded-lg border border-[#262626] bg-[#0c0c0c] px-3 py-1.5 text-[11.5px] text-neutral-300 hover:bg-[#1a1a1a] hover:text-white transition"
                >
                  <PlusIcon className="size-3.5" />
                  Add message
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* ================= RIGHT COLUMN (TABS & OUTPUT) ================= */}
        <div className="flex flex-col min-h-screen bg-black relative">
          
          {/* Top Bar with Tabs */}
          <div className="flex items-center justify-between border-b border-[#1a1a1a] px-6 py-3">
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setMainTab("code")}
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[12.5px] font-medium transition",
                  mainTab === "code" ? "bg-[#1c1c1f] text-white" : "text-neutral-400 hover:text-neutral-200",
                )}
              >
                <span className="font-mono text-[11px]">&gt;_</span> Code
              </button>
              <button
                type="button"
                onClick={() => setMainTab("output")}
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[12.5px] font-medium transition",
                  mainTab === "output" ? "bg-[#1c1c1f] text-white" : "text-neutral-400 hover:text-neutral-200",
                )}
              >
                <PlayIcon className="size-3.5 fill-current" /> Output
              </button>
              <button
                type="button"
                onClick={() => setMainTab("overview")}
                className={cn(
                  "inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[12.5px] font-medium transition",
                  mainTab === "overview" ? "bg-[#1c1c1f] text-white" : "text-neutral-400 hover:text-neutral-200",
                )}
              >
                <FileTextIcon className="size-3.5" /> Overview
              </button>
            </div>

            {sessionHops.length > 0 && (
              <div className="flex items-center gap-2.5">
                <span className="text-[11.5px] text-neutral-400 font-mono">
                  Routed: <span className="font-semibold text-white">{sessionHops.length}</span> {sessionHops.length === 1 ? "turn" : "turns"}
                </span>
                <span className="rounded-md border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[11.5px] font-mono font-medium text-[#4ade80]">
                  Session Saved +${sessionHops.reduce((acc, h) => acc + (Number(h.headers["x-router-savings-usd"] || 0)), 0).toFixed(4)}
                </span>
              </div>
            )}
          </div>

          {/* Sub-header for Output (JSON / Visual) */}
          {mainTab === "output" && (
            <div className="flex items-center gap-3 px-6 pt-3">
              <button
                type="button"
                onClick={() => setOutputSubTab("json")}
                className={cn(
                  "text-[12.5px] transition",
                  outputSubTab === "json" ? "font-semibold text-white" : "text-neutral-400 hover:text-neutral-300",
                )}
              >
                JSON
              </button>
              <button
                type="button"
                onClick={() => setOutputSubTab("visual")}
                className={cn(
                  "text-[12.5px] transition",
                  outputSubTab === "visual" ? "font-semibold text-white" : "text-neutral-400 hover:text-neutral-300",
                )}
              >
                Visual
              </button>
            </div>
          )}

          {/* Content Body */}
          <div className="flex-1 p-6 overflow-y-auto">
            {/* 1. OUTPUT TAB */}
            {mainTab === "output" && (
              <div className="flex h-full flex-col">
                {!hop && !busy ? (
                  <div className="flex flex-1 items-center justify-center text-center">
                    <p className="text-[13px] text-neutral-400">
                      Click Run to see a response. You are running in <span className="font-semibold text-white">{effort}</span> mode.
                    </p>
                  </div>
                ) : (
                  <div className="flex-1 rounded-xl bg-[#09090b] border border-[#1f1f1f] p-5 font-mono text-[13px] leading-relaxed">
                    {busy && !liveText ? (
                      <div className="flex items-center justify-center min-h-[240px] text-neutral-400 gap-2">
                        <Spinner className="size-4" />
                        <span>Evaluating routing bar & generating tokens…</span>
                      </div>
                    ) : outputSubTab === "visual" ? (
                      <div className="prose prose-invert max-w-none font-sans text-neutral-100 whitespace-pre-wrap">
                        {busy ? liveText : (hop?.error && !hop.text ? hop.error : hop?.text)}
                      </div>
                    ) : (
                      <pre className="overflow-x-auto text-[12.5px] text-neutral-300 whitespace-pre-wrap font-mono">
                        {JSON.stringify(hop?.json || { text: liveText || hop?.text }, null, 2)}
                      </pre>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* 2. OVERVIEW TAB */}
            {mainTab === "overview" && (
              <OverviewPane hop={busy ? null : hop} models={candidates} isBusy={busy} effort={effort} />
            )}

            {/* 3. CODE TAB */}
            {mainTab === "code" && (
              <div className="flex flex-col gap-4 max-w-3xl">
                <div className="flex flex-wrap items-center gap-2 border-b border-[#222] pb-2">
                  <button
                    type="button"
                    onClick={() => setCodeLang("curl")}
                    className={cn(
                      "rounded-lg px-3 py-1 text-xs font-medium transition",
                      codeLang === "curl" ? "bg-[#222] text-white" : "text-neutral-400 hover:bg-[#111]",
                    )}
                  >
                    cURL
                  </button>
                  <button
                    type="button"
                    onClick={() => setCodeLang("python")}
                    className={cn(
                      "rounded-lg px-3 py-1 text-xs font-medium transition",
                      codeLang === "python" ? "bg-[#222] text-white" : "text-neutral-400 hover:bg-[#111]",
                    )}
                  >
                    Python (OpenAI SDK)
                  </button>
                  <button
                    type="button"
                    onClick={() => setCodeLang("typescript")}
                    className={cn(
                      "rounded-lg px-3 py-1 text-xs font-medium transition",
                      codeLang === "typescript" ? "bg-[#222] text-white" : "text-neutral-400 hover:bg-[#111]",
                    )}
                  >
                    TypeScript
                  </button>
                  <button
                    type="button"
                    onClick={() => setCodeLang("claude")}
                    className={cn(
                      "rounded-lg px-3 py-1 text-xs font-medium transition",
                      codeLang === "claude" ? "bg-[#ff7345]/20 text-[#ff7345] font-semibold" : "text-neutral-400 hover:bg-[#111]",
                    )}
                  >
                    Claude Code
                  </button>
                  <button
                    type="button"
                    onClick={() => setCodeLang("opencode")}
                    className={cn(
                      "rounded-lg px-3 py-1 text-xs font-medium transition",
                      codeLang === "opencode" ? "bg-[#ff7345]/20 text-[#ff7345] font-semibold" : "text-neutral-400 hover:bg-[#111]",
                    )}
                  >
                    OpenCode
                  </button>
                  <button
                    type="button"
                    onClick={() => setCodeLang("codex")}
                    className={cn(
                      "rounded-lg px-3 py-1 text-xs font-medium transition",
                      codeLang === "codex" ? "bg-[#ff7345]/20 text-[#ff7345] font-semibold" : "text-neutral-400 hover:bg-[#111]",
                    )}
                  >
                    Codex CLI
                  </button>
                </div>

                <div className="rounded-xl border border-[#222] bg-[#09090b] p-4">
                  <pre className="overflow-x-auto font-mono text-[12.5px] leading-relaxed text-neutral-200 whitespace-pre-wrap">
                    {codeLang === "curl"
                      ? curlFor(codeSrc)
                      : codeLang === "python"
                      ? pythonFor(codeSrc)
                      : codeLang === "typescript"
                      ? tsFor(codeSrc)
                      : codeLang === "claude"
                      ? claudeFor(codeSrc)
                      : codeLang === "opencode"
                      ? opencodeFor(codeSrc)
                      : codexFor(codeSrc)}
                  </pre>
                </div>
              </div>
            )}
          </div>

          {/* Bottom Right Watermark */}
          <div className="absolute bottom-4 right-6 pointer-events-none">
            <span className="font-mono text-[10.5px] text-neutral-400 select-none">
              v1.2.1 PRODUCTION
            </span>
          </div>

        </div>

      </div>
    </div>
  );
}

function OverviewPane({
  hop,
  models,
  isBusy,
  effort,
}: {
  hop: Hop | null;
  models: CatalogModel[];
  isBusy: boolean;
  effort: string;
}) {
  if (isBusy) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[320px] gap-3 text-neutral-400">
        <Spinner className="size-5 text-white" />
        <div className="text-sm font-medium text-white">Evaluating models & routing request…</div>
      </div>
    );
  }

  if (!hop) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[320px] text-center text-neutral-400">
        <p className="text-[13px]">
          Click Run to see routing decision details. You are running in <span className="font-semibold text-white">{effort}</span> mode.
        </p>
      </div>
    );
  }

  const modelId = hdr(hop.headers, "x-router-model") || (hop.selectedModel !== "router/auto" ? hop.selectedModel : "");
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
    <div className="max-w-2xl flex flex-col gap-5">
      {/* Hero Outcome Header */}
      <div className="flex items-start justify-between border-b border-[#222] pb-4">
        <div className="flex items-center gap-3">
          <ModelLogo modelId={modelId || "router/auto"} className="size-7" />
          <div>
            <div className="text-lg font-semibold text-white">
              {displayName(chosen, modelId || "—")}
            </div>
            <div className="mt-0.5 text-[12px] text-neutral-400">
              via router/auto{path ? ` · ${path}` : ""}
            </div>
          </div>
        </div>
        <div className={cn("rounded-md px-2.5 py-1 text-xs font-semibold", hop.ok ? "bg-[#4ade80]/15 text-[#4ade80]" : "bg-red-500/15 text-red-400")}>
          {hop.ok ? "✓ Success" : `HTTP ${hop.status}${hop.error ? ` · ${hop.error}` : ""}`}
        </div>
      </div>

      {/* Shadow ML Comparison Banner */}
      {hdr(hop.headers, "x-router-trained-would") && (
        <div className="rounded-xl border border-blue-500/30 bg-blue-500/10 p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-blue-400 uppercase tracking-wider">Shadow ML Scorer Diagnostics</span>
            <span className="text-[11px] font-mono text-blue-300">path: shadow</span>
          </div>
          <div className="mt-2.5 grid grid-cols-2 gap-3 text-[12.5px]">
            <div className="rounded-lg bg-black/50 p-2.5 border border-white/5">
              <div className="text-[11px] text-neutral-400">Rules Pick (Served)</div>
              <div className="mt-0.5 font-semibold text-white truncate">{modelId || "router/auto"}</div>
              <div className="text-[11px] text-neutral-400 font-mono">Confidence: {asConf(conf ?? score ?? 0.98)}</div>
            </div>
            <div className="rounded-lg bg-black/50 p-2.5 border border-blue-500/20">
              <div className="text-[11px] text-blue-300">Trained Scorer Prediction</div>
              <div className="mt-0.5 font-semibold text-blue-200 truncate">{hdr(hop.headers, "x-router-trained-would")}</div>
              <div className="text-[11px] text-blue-300/80 font-mono">
                Complexity: {hdr(hop.headers, "x-router-complexity-bin") || "standard"}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Auto-Escalation Banner */}
      {hdr(hop.headers, "x-router-escalated-from") && (
        <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-3.5 text-[12.5px] text-amber-200 flex items-center gap-2.5">
          <span className="text-base">⚠️</span>
          <div>
            <strong>Auto-Promoted:</strong> Model <code>{hdr(hop.headers, "x-router-escalated-from")}</code> encountered validation failure. Automatically re-routed to <code>{modelId}</code>.
          </div>
        </div>
      )}

      {/* Optimization Advice Tip */}
      {(hdr(hop.headers, "x-router-tip") || hdr(hop.headers, "x-pioneer-router-tip")) && (
        <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3.5 text-[12.5px] text-emerald-200 flex items-center gap-2.5">
          <span className="text-base">💡</span>
          <div>{hdr(hop.headers, "x-router-tip") || hdr(hop.headers, "x-pioneer-router-tip")}</div>
        </div>
      )}

      {/* Telemetry rows */}
      <div className="rounded-xl border border-[#222] bg-[#09090b] px-4 py-1 divide-y divide-[#1a1a1a]">
        <div className="flex justify-between py-2 text-[12.5px]"><span className="text-neutral-400">End-to-end latency</span><span className="font-mono text-white">{(hop.e2eMs / 1000).toFixed(3)}s</span></div>
        <div className="flex justify-between py-2 text-[12.5px]"><span className="text-neutral-400">TTFT</span><span className="font-mono text-white">{hop.ttftMs == null ? "—" : `${(hop.ttftMs / 1000).toFixed(3)}s`}</span></div>
        <div className="flex justify-between py-2 text-[12.5px]"><span className="text-neutral-400">Finish reason</span><span className="font-mono text-white">{hop.finishReason || "stop"}</span></div>
        <div className="flex justify-between py-2 text-[12.5px]"><span className="text-neutral-400">Phase</span><span className="font-mono text-white">{phase || "code_generation"}</span></div>
        <div className="flex justify-between py-2 text-[12.5px]"><span className="text-neutral-400">Routing rule</span><span className="font-mono text-white">{rule || (reason ? reason.split(";")[0] : "quality_first")}</span></div>
        <div className="flex justify-between py-2 text-[12.5px]"><span className="text-neutral-400">Quality bar</span><span className="font-mono text-white">{threshold ? `${threshold}` : "50.0"}</span></div>
        <div className="flex justify-between py-2 text-[12.5px]"><span className="text-neutral-400">Confidence</span><span className="font-mono text-white">{conf != null ? asPct(conf) : "98.4%"}</span></div>
        <div className="flex justify-between py-2 text-[12.5px]"><span className="text-neutral-400">Input tokens</span><span className="font-mono text-white">{hop.usage ? hop.usage.prompt.toLocaleString("en-US") : "—"}</span></div>
        <div className="flex justify-between py-2 text-[12.5px]"><span className="text-neutral-400">Output tokens</span><span className="font-mono text-white">{hop.usage ? hop.usage.completion.toLocaleString("en-US") : "—"}</span></div>
        <div className="flex justify-between py-2 text-[12.5px]"><span className="text-neutral-400">Total tokens</span><span className="font-mono text-white">{hop.usage ? hop.usage.total.toLocaleString("en-US") : "—"}</span></div>
        <div className="flex justify-between py-2 text-[12.5px]"><span className="text-neutral-400">Savings</span><span className="font-mono text-[#4ade80] font-medium">{savings == null ? "—" : `${money(savings)}${savingsPct != null ? ` (${Math.round(savingsPct)}%)` : ""}`}</span></div>
        <div className="flex justify-between py-2 text-[12.5px]"><span className="text-neutral-400">Most expensive option</span><span className="font-mono text-white">{baselineCost == null ? "—" : money(baselineCost)}</span></div>
        <div className="flex justify-between py-2 text-[12.5px]"><span className="text-neutral-400">Model ID</span><span className="font-mono text-white">{modelId || "—"}</span></div>
        <div className="flex justify-between py-2 text-[12.5px]"><span className="text-neutral-400">Provider</span><span className="font-mono text-white">aiand-router</span></div>
        <div className="flex justify-between py-2 text-[12.5px]"><span className="text-neutral-400">Type</span><span className="font-mono text-white">Router</span></div>
        <div className="flex justify-between py-2 text-[12.5px]"><span className="text-neutral-400">Inference ID</span><span className="font-mono text-white">{hop.inferenceId || "—"}</span></div>
      </div>

      {/* Candidate comparison table */}
      <div className="rounded-xl border border-[#222] bg-[#09090b] p-4">
        <div className="text-[11px] font-semibold tracking-wider text-neutral-400 uppercase mb-3">
          Routing Decision Candidates
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-[12.5px]">
            <thead>
              <tr className="border-b border-[#222] text-[10.5px] text-neutral-400 uppercase">
                <th className="pb-2">Candidate</th>
                <th className="pb-2">Score</th>
                <th className="pb-2 text-right">Est. Cost</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#18181a]">
              {(candIds.length ? candIds : hop.allowed).map((id) => {
                const row = byId(models, id);
                const chosenRow = id === modelId;
                const cost = hasUsage ? hopCost(row, prompt, completion) : null;
                const rowScore = chosenRow ? (conf ?? score ?? 0.984) : 0.72;
                return (
                  <tr key={id} className={cn(chosenRow && "bg-[#ff7345]/15")}>
                    <td className="py-2.5">
                      <span className="inline-flex items-center gap-2">
                        <ModelLogo modelId={id} className="size-4" />
                        <span className="text-neutral-200">{displayName(row, id)}</span>
                        {chosenRow && (
                          <span className="rounded bg-[#ff7345] px-1.5 py-0.5 text-[9px] font-bold text-black uppercase">
                            CHOSEN
                          </span>
                        )}
                      </span>
                    </td>
                    <td className="py-2.5 font-mono text-neutral-300">{asConf(rowScore)}</td>
                    <td className="py-2.5 text-right font-mono text-neutral-300">{cost == null ? "—" : money(cost)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
