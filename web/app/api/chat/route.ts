import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

type ChatBody = {
  prompt?: string;
  system?: string;
  effort?: string;
  allowedModels?: string[];
  stream?: boolean;
  jsonMode?: boolean;
};

function routerHeaders(src: Headers): Record<string, string> {
  const out: Record<string, string> = {};
  src.forEach((v, k) => {
    if (k.toLowerCase().startsWith("x-router-")) out[k.toLowerCase()] = v;
  });
  return out;
}

function messages(body: ChatBody) {
  const prompt = (body.prompt || "").trim();
  const system = (body.system || "").trim();
  const out: { role: string; content: string }[] = [];
  if (system) out.push({ role: "system", content: system });
  out.push({ role: "user", content: prompt });
  return out;
}

export async function POST(req: Request) {
  const body = (await req.json().catch(() => ({}))) as ChatBody;
  const prompt = (body.prompt || "").trim();
  if (!prompt) {
    return NextResponse.json(
      { ok: false, status: 400, headers: {}, json: null, error: "prompt required" },
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
  if (body.allowedModels?.length) headers["x-allowed-models"] = body.allowedModels.join(",");

  const payload: Record<string, unknown> = {
    model: "router/auto",
    messages: messages(body),
    stream: Boolean(body.stream),
  };
  if (body.jsonMode) payload.response_format = { type: "json_object" };

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
      error: r.ok ? undefined : r.statusText,
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
