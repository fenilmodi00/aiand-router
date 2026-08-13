import { MIX_COLORS, type Candidate, type CandidateMix } from "@/lib/types";
import { pct } from "@/lib/format";

export type MixRow = {
  id: string;
  display_name: string;
  count: number;
  pct: number;
};

/** Last-resort catalog so the Sankey never collapses to two nodes if overview is empty. */
const FALLBACK_ROWS: MixRow[] = [
  { id: "qwen/qwen3.6-27b", display_name: "Qwen 3.6 27B", count: 0, pct: 0 },
  { id: "deepseek-ai/deepseek-v4-flash", display_name: "DeepSeek V4 Flash", count: 0, pct: 0 },
  { id: "google/gemma-4-31b-it", display_name: "Gemma 4 31B", count: 0, pct: 0 },
  { id: "openai/gpt-oss-120b", display_name: "GPT OSS 120B", count: 0, pct: 0 },
  { id: "moonshotai/kimi-k2.7-code", display_name: "Kimi K2.7 Code", count: 0, pct: 0 },
  { id: "deepseek-ai/deepseek-v4-pro", display_name: "DeepSeek V4 Pro", count: 0, pct: 0 },
  { id: "zai-org/glm-5.2", display_name: "GLM 5.2", count: 0, pct: 0 },
  { id: "moonshotai/kimi-k3", display_name: "Kimi K3", count: 0, pct: 0 },
  { id: "motif-technologies/motif-3", display_name: "Motif 3", count: 0, pct: 0 },
];

export function mixRows(candidates: Candidate[], mix: CandidateMix[]): MixRow[] {
  const byId = Object.fromEntries(mix.map((m) => [m.id, m]));
  const seen = new Set<string>();
  const rows: MixRow[] = [];
  for (const c of candidates) {
    if (c.enabled === false) continue;
    rows.push({
      id: c.id,
      display_name: c.display_name,
      count: byId[c.id]?.count ?? 0,
      pct: byId[c.id]?.pct ?? 0,
    });
    seen.add(c.id);
  }
  for (const m of mix) {
    if (seen.has(m.id)) continue;
    rows.push({ id: m.id, display_name: m.display_name, count: m.count, pct: m.pct });
    seen.add(m.id);
  }
  return rows;
}

/** Stable accent by model id. Unknown ids walk MIX_COLORS. */
export function accentFor(id: string, i: number): string {
  const s = id.toLowerCase();
  if (s.includes("flash")) return "var(--blue)";
  if (s.includes("glm")) return "var(--orange)";
  if (s.includes("pro")) return "var(--blue)";
  if (s.includes("motif")) return "var(--green)";
  if (s.includes("kimi")) return "var(--tan)";
  if (s.includes("qwen")) return "var(--teal)";
  if (s.includes("gemma")) return "var(--emerald)";
  if (s.includes("oss")) return "var(--teal)";
  return MIX_COLORS[i % MIX_COLORS.length]!;
}

export function RoutingPipeline({
  requests,
  rows,
}: {
  requests: number;
  rows: MixRow[];
}) {
  const shown = rows.length ? rows : FALLBACK_ROWS;
  const n = shown.length;
  const gap = 63;
  const startY = 40;
  const modelH = 46;
  const nodeH = 66;
  const nodeW = 170;
  const modelW = 200;
  const leftX = 20;
  const routerX = 500;
  const modelX = 980;
  const height = startY + Math.max(n - 1, 0) * gap + modelH + 33;
  const routerY = height / 2;
  const orangeW = requests > 0 ? Math.min(26, 12 + Math.sqrt(requests) * 2) : 14;

  return (
    <div className="card pipeline">
      <svg
        viewBox={`0 0 1180 ${height}`}
        width="100%"
        preserveAspectRatio="xMidYMid meet"
        role="img"
        aria-label="Routing pipeline flow diagram"
      >
        <defs>
          <clipPath id="rpNodeClip">
            <rect width={nodeW} height={nodeH} rx="10" />
          </clipPath>
          <clipPath id="rpModelClip">
            <rect width={modelW} height={modelH} rx="10" />
          </clipPath>
        </defs>

        <path
          d={`M ${leftX + nodeW} ${routerY} C ${leftX + nodeW + 140} ${routerY}, ${routerX - 150} ${routerY}, ${routerX} ${routerY}`}
          stroke="var(--orange)"
          strokeWidth={orangeW}
          fill="none"
          opacity="0.85"
          strokeLinecap="round"
        />

        <g fill="none" opacity="0.75" strokeLinecap="round">
          {shown.map((row, i) => {
            const my = startY + i * gap + modelH / 2;
            const w = row.count > 0 ? Math.max(2.5, Math.min(12, 2.5 + row.pct / 10)) : 2.5;
            return (
              <path
                key={row.id}
                d={`M ${routerX + nodeW} ${routerY} C ${routerX + nodeW + 140} ${routerY}, ${modelX - 130} ${my}, ${modelX} ${my}`}
                stroke={accentFor(row.id, i)}
                strokeWidth={w}
              />
            );
          })}
        </g>

        <g transform={`translate(${leftX}, ${routerY - nodeH / 2})`}>
          <rect width={nodeW} height={nodeH} rx="10" fill="#151517" stroke="#232329" />
          <rect width="4" height={nodeH} fill="var(--orange)" clipPath="url(#rpNodeClip)" />
          <text x="20" y="29" fill="var(--fg)" fontSize="13.5" fontWeight="600">
            Requests
          </text>
          <text x="20" y="47" fill="var(--muted)" fontSize="11.5">
            {requests} sampled
          </text>
        </g>

        <g transform={`translate(${routerX}, ${routerY - nodeH / 2})`}>
          <rect width={nodeW} height={nodeH} rx="10" fill="#151517" stroke="#232329" />
          <rect width="4" height={nodeH} fill="var(--green)" clipPath="url(#rpNodeClip)" />
          <text x="20" y="29" fill="var(--fg)" fontSize="13.5" fontWeight="600">
            router/auto
          </text>
          <text x="20" y="47" fill="var(--muted)" fontSize="11.5">
            router
          </text>
        </g>

        {shown.map((row, i) => {
          const y = startY + i * gap;
          const color = accentFor(row.id, i);
          const label =
            row.display_name.length > 22 ? `${row.display_name.slice(0, 20)}…` : row.display_name;
          return (
            <g key={row.id} transform={`translate(${modelX}, ${y})`}>
              <rect width={modelW} height={modelH} rx="10" fill="#151517" stroke="#232329" />
              <rect width="4" height={modelH} fill={color} clipPath="url(#rpModelClip)" />
              <circle cx="20" cy={modelH / 2} r="4.5" fill={color} />
              <text x="36" y="27" fill="var(--fg)" fontSize="13" fontWeight="500">
                {label}
              </text>
              <text
                x={modelW - 14}
                y="27"
                fill="var(--muted)"
                fontSize="11.5"
                textAnchor="end"
                fontFamily="var(--font-mono), ui-monospace, monospace"
              >
                {pct(row.pct)} · {row.count}
              </text>
            </g>
          );
        })}
      </svg>
      <p className="pipeline-desc">
        Routes each request to the cheapest candidate that still meets the quality bar.
      </p>
    </div>
  );
}
