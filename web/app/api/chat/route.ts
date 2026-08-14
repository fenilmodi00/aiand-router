import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

type ChatMessage = { role: string; content: string };

type ChatBody = {
  model?: string;
  prompt?: string;
  system?: string;
  messages?: ChatMessage[];
  effort?: string;
  phase?: string;
  latencyLimit?: number;
  trainedPath?: string;
  allowedModels?: string[];
  stream?: boolean;
  jsonMode?: boolean;
  temperature?: number;
  max_tokens?: number;
  tools?: unknown[];
};

function routerHeaders(src: Headers): Record<string, string> {
  const out: Record<string, string> = {};
  src.forEach((v, k) => {
    const lk = k.toLowerCase();
    if (
      lk.startsWith("x-router-") ||
      lk.startsWith("pioneer_") ||
      lk === "content-type" ||
      lk.includes("tip")
    ) {
      out[lk] = v;
    }
  });
  return out;
}

function buildMessages(body: ChatBody): ChatMessage[] {
  if (Array.isArray(body.messages) && body.messages.length > 0) {
    const list = [...body.messages];
    if (body.system?.trim() && !list.some((m) => m.role === "system")) {
      list.unshift({ role: "system", content: body.system.trim() });
    }
    return list;
  }
  const prompt = (body.prompt || "").trim();
  const system = (body.system || "").trim();
  const out: ChatMessage[] = [];
  if (system) out.push({ role: "system", content: system });
  if (prompt) out.push({ role: "user", content: prompt });
  return out;
}

export async function POST(req: Request) {
  const body = (await req.json().catch(() => ({}))) as ChatBody;
  const msgs = buildMessages(body);
  if (msgs.length === 0) {
    return NextResponse.json(
      { ok: false, status: 400, headers: {}, json: null, error: "prompt or messages required" },
      { status: 400 },
    );
  }

  const base = (process.env.ROUTER_BASE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
  const key = process.env.ROUTER_API_KEY || "";
  const headers: Record<string, string> = {
    Authorization: `Bearer ${key}`,
    "Content-Type": "application/json",
  };
  if (body.effort) headers["x-routing-effort"] = body.effort;
  if (body.phase && body.phase !== "auto") headers["x-agent-phase"] = body.phase;
  if (typeof body.latencyLimit === "number" && body.latencyLimit > 0) {
    headers["x-latency-limit"] = String(body.latencyLimit);
  }
  if (body.trainedPath) headers["x-routing-path"] = body.trainedPath;
  if (body.allowedModels?.length) headers["x-allowed-models"] = body.allowedModels.join(",");

  const payload: Record<string, unknown> = {
    model: body.model || "router/auto",
    messages: msgs,
    stream: Boolean(body.stream),
  };
  if (body.jsonMode) payload.response_format = { type: "json_object" };
  if (typeof body.temperature === "number") payload.temperature = body.temperature;
  if (typeof body.max_tokens === "number") payload.max_tokens = body.max_tokens;
  if (Array.isArray(body.tools) && body.tools.length > 0) payload.tools = body.tools;

  try {
    const r = await fetch(`${base}/v1/chat/completions`, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
    });
    const hop = routerHeaders(r.headers);
    const ctype = r.headers.get("content-type") || "";
    if (body.stream && ctype.includes("text/event-stream") && r.body) {
      const out = new Headers({
        "Content-Type": "text/event-stream; charset=utf-8",
        "Cache-Control": "no-cache, no-transform",
        "X-Accel-Buffering": "no",
      });
      for (const [k, v] of Object.entries(hop)) out.set(k, v);
      return new Response(r.body, { status: r.status, headers: out });
    }
    const json = await r.json().catch(() => null);
    return NextResponse.json({
      ok: r.ok,
      status: r.status,
      headers: hop,
      json,
      error: r.ok ? undefined : r.statusText || "Request failed",
    });
  } catch (e) {
    return NextResponse.json({
      ok: false,
      status: 0,
      headers: {},
      json: null,
      error: e instanceof Error ? e.message : "fetch failed",
    });
  }
}
