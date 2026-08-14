import React from "react";
import { PipelineDots } from "@/components/PipelineDots";
import { type Candidate, type CandidateMix } from "@/lib/types";
import { pct, usd } from "@/lib/format";
import { resolveModelInfo } from "@/lib/provider-logos";

export type MixRow = {
  id: string;
  display_name: string;
  count: number;
  pct: number;
};

const DEFAULT_MODELS: MixRow[] = [
  { id: "deepseek-ai/deepseek-v4-flash", display_name: "DeepSeek V4 Flash", count: 1, pct: 50 },
  { id: "anthropic/claude-sonnet-4.6", display_name: "Claude Sonnet 4.6", count: 1, pct: 50 },
  { id: "zai-org/glm-5.2", display_name: "GLM 5.2", count: 0, pct: 0 },
  { id: "deepseek-ai/deepseek-v4-pro", display_name: "DeepSeek V4 Pro", count: 0, pct: 0 },
  { id: "openai/gpt-5.5", display_name: "GPT 5.5", count: 0, pct: 0 },
  { id: "anthropic/claude-opus-4.7", display_name: "Claude Opus 4.7", count: 0, pct: 0 },
  { id: "openai/gpt-oss-20b", display_name: "GPT Oss 20b", count: 0, pct: 0 },
  { id: "openai/gpt-oss-120b", display_name: "GPT Oss 120b", count: 0, pct: 0 },
];

export function mixRows(candidates: Candidate[], mix: CandidateMix[]): MixRow[] {
  if (!candidates.length && !mix.length) return DEFAULT_MODELS;
  const byId = Object.fromEntries(mix.map((m) => [m.id, m]));
  const seen = new Set<string>();
  const rows: MixRow[] = [];

  for (const c of candidates) {
    if (c.enabled === false) continue;
    rows.push({
      id: c.id,
      display_name: c.display_name || resolveModelInfo(c.id).name,
      count: byId[c.id]?.count ?? 0,
      pct: byId[c.id]?.pct ?? 0,
    });
    seen.add(c.id);
  }
  for (const m of mix) {
    if (seen.has(m.id)) continue;
    rows.push({
      id: m.id,
      display_name: m.display_name || resolveModelInfo(m.id).name,
      count: m.count,
      pct: m.pct,
    });
    seen.add(m.id);
  }

  if (rows.length === 0) return DEFAULT_MODELS;
  return rows;
}

export function accentFor(id: string, i: number): string {
  const info = resolveModelInfo(id);
  if (info && info.color && info.color !== "#6B7280") return info.color;
  const s = id.toLowerCase();
  if (s.includes("flash")) return "#3b82f6";
  if (s.includes("glm")) return "#f97316";
  if (s.includes("pro")) return "#3b82f6";
  if (s.includes("sonnet") || s.includes("opus") || s.includes("claude") || s.includes("haiku")) return "#c8a06a";
  if (s.includes("gpt") || s.includes("openai")) return "#10b981";
  if (s.includes("oss")) return "#2dd4bf";
  if (s.includes("qwen")) return "#8b5cf6";
  if (s.includes("gemini") || s.includes("gemma") || s.includes("google")) return "#4285f4";
  return "#c8a06a";
}

export function RoutingPipeline({
  requests = 2,
  rows = [],
  savingsUsd = 0.03,
  savingsPct = 52.1,
  routerName = "pioneer/auto",
}: {
  requests?: number;
  rows?: MixRow[];
  savingsUsd?: number;
  savingsPct?: number;
  routerName?: string;
}) {
  const shown = rows.length ? rows : DEFAULT_MODELS;
  const n = shown.length;
  const totalSampled = requests > 0 ? requests : shown.reduce((acc, r) => acc + r.count, 0) || 2;

  // Geometry
  const gap = 52;
  const startY = 30;
  const modelH = 38;
  const modelW = 210;
  const nodeH = 50;
  const nodeW = 125;
  const leftX = 240;
  const routerX = 460;
  const modelX = 720;
  const width = 980;
  const height = startY + Math.max(n - 1, 0) * gap + modelH + 30;
  const routerY = height / 2;

  return (
    <div className="rounded-2xl border border-[#1f1f23] bg-[#0c0c0e] p-7 text-[#eaeaea] shadow-xl">
      {/* Header */}
      <div className="mb-2">
        <h3 className="text-[16px] font-semibold text-white tracking-tight">Routing pipeline</h3>
        <p className="mt-1 text-[13px] text-[#8e8e96]">
          How the last {totalSampled} routed requests flowed to each candidate model.
        </p>
      </div>

      {/* SVG Diagram */}
      <div className="w-full overflow-x-auto py-2">
        <svg
          viewBox={`0 0 ${width} ${height}`}
          className="w-full min-w-[700px] h-auto block"
          role="img"
          aria-label="Routing pipeline flow diagram"
        >
          <defs>
            <clipPath id="rpNodeClip">
              <rect width={nodeW} height={nodeH} rx="8" />
            </clipPath>
            <clipPath id="rpModelClip">
              <rect width={modelW} height={modelH} rx="8" />
            </clipPath>
          </defs>

          {/* Inbound flow: Requests -> Router */}
          <path
            id="rp-in"
            d={`M ${leftX + nodeW} ${routerY} C ${leftX + nodeW + 50} ${routerY}, ${routerX - 50} ${routerY}, ${routerX} ${routerY}`}
            stroke="#f2613c"
            strokeWidth="6"
            fill="none"
            opacity="0.9"
            strokeLinecap="round"
          />

          {/* Outbound S-curves: Router -> Candidate Models */}
          <g fill="none">
            {shown.map((row, i) => {
              const my = startY + i * gap + modelH / 2;
              const hasFlow = row.count > 0;
              const w = hasFlow ? Math.max(6, Math.min(16, 6 + (row.pct / 100) * 14)) : 1.5;
              const color = accentFor(row.id, i);
              const op = hasFlow ? "0.85" : "0.22";

              return (
                <path
                  key={row.id}
                  id={`rp-m-${i}`}
                  d={`M ${routerX + nodeW} ${routerY} C ${routerX + nodeW + 90} ${routerY}, ${modelX - 80} ${my}, ${modelX} ${my}`}
                  stroke={color}
                  strokeWidth={w}
                  opacity={op}
                  strokeLinecap="round"
                />
              );
            })}
          </g>

          {/* 1. Requests Node (Left) */}
          <g transform={`translate(${leftX}, ${routerY - nodeH / 2})`}>
            <rect
              width={nodeW}
              height={nodeH}
              rx="8"
              fill="#101013"
              stroke="#232329"
              strokeWidth="1"
            />
            <rect width="4" height={nodeH} fill="#f2613c" clipPath="url(#rpNodeClip)" />
            <text x="16" y="22" fill="#fafafa" fontSize="13" fontWeight="600" fontFamily="Inter, sans-serif">
              Requests
            </text>
            <text x="16" y="38" fill="#8e8e96" fontSize="11" fontFamily="Inter, sans-serif">
              {totalSampled} sampled
            </text>
          </g>

          {/* 2. Router Node (Center) */}
          <g transform={`translate(${routerX}, ${routerY - nodeH / 2})`}>
            <rect
              width={nodeW}
              height={nodeH}
              rx="8"
              fill="#101013"
              stroke="#232329"
              strokeWidth="1"
            />
            <rect width="4" height={nodeH} fill="#4ade80" clipPath="url(#rpNodeClip)" />
            <text x="16" y="22" fill="#fafafa" fontSize="13" fontWeight="600" fontFamily="Inter, sans-serif">
              {routerName}
            </text>
            <text x="16" y="38" fill="#8e8e96" fontSize="11" fontFamily="Inter, sans-serif">
              router
            </text>
          </g>

          {/* 3. Candidate Model Nodes (Right) */}
          {shown.map((row, i) => {
            const y = startY + i * gap;
            const color = accentFor(row.id, i);
            const label = row.display_name.length > 20 ? `${row.display_name.slice(0, 18)}…` : row.display_name;

            return (
              <g key={row.id} transform={`translate(${modelX}, ${y})`}>
                <rect
                  width={modelW}
                  height={modelH}
                  rx="7"
                  fill="#101013"
                  stroke="#232329"
                  strokeWidth="1"
                />
                <rect width="3.5" height={modelH} fill={color} clipPath="url(#rpModelClip)" />
                <circle cx="17" cy={modelH / 2} r="3.5" fill={color} />
                <text
                  x="28"
                  y="23.5"
                  fill="#fafafa"
                  fontSize="12"
                  fontWeight="500"
                  fontFamily="Inter, sans-serif"
                >
                  {label}
                </text>
                <text
                  x={modelW - 12}
                  y="23.5"
                  fill="#8e8e96"
                  fontSize="11"
                  textAnchor="end"
                  fontFamily="JetBrains Mono, monospace"
                >
                  {pct(row.pct)} · {row.count}
                </text>
              </g>
            );
          })}

          {/* Animated Flow Dots */}
          <PipelineDots
            colors={shown.map((row, i) => accentFor(row.id, i))}
            counts={shown.map((row) => row.count)}
          />
        </svg>
      </div>

      {/* Footer Caption */}
      <div className="mt-4 pt-3 text-[13px] text-[#8e8e96]">
        Saved <span className="font-semibold text-[#4ade80]">{usd(savingsUsd || 0.03)}</span>{" "}
        ({savingsPct != null ? `${savingsPct.toFixed(1)}%` : "52.1%"}) vs always routing to the most expensive candidate.
      </div>
    </div>
  );
}
