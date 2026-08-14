"use client";

import { useMemo, useState } from "react";
import { PercentIcon } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { shortTs } from "@/lib/format";
import type { UsageBucket } from "@/lib/types";

const VW = 720;
const VH = 248;
const L = 56;
const R = 708;
const T = 20;
const B = 214;

const GREY_BASE = "#8e8e96";
const BLUE_ROUTED = "#3b82f6";

type Pt = { ts: string; label: string; spend: number; baseline: number };

function ago(ts: string, nowTs: string): string {
  const t = new Date(ts).getTime();
  const now = new Date(nowTs).getTime();
  if (!Number.isFinite(t) || !Number.isFinite(now)) return "—";
  const ms = now - t;
  if (ms < 90 * 60 * 1000) return "Now";
  const h = ms / 3_600_000;
  if (h < 36) return `${Math.round(h)}h ago`;
  const d = h / 24;
  if (d < 11) return `${Math.round(d)}d ago`;
  const w = d / 7;
  if (w < 5) return `${Math.round(w)}w ago`;
  return `${Math.max(1, Math.round(d / 30))}mo ago`;
}

function moneyTicks(max: number): number[] {
  const raw = (max > 0 ? max : 0.05) * 1.2;
  const pow = 10 ** Math.floor(Math.log10(raw));
  const n = raw / pow;
  const nice = n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10;
  const top = nice * pow;
  const step = top / 4;
  return [0, step, 2 * step, 3 * step, top];
}

function axisUsd(n: number): string {
  if (n === 0) return "$0.00";
  if (n < 0.1) return `$${n.toFixed(2)}`;
  return `$${n.toFixed(2)}`;
}

function tipUsd(n: number): string {
  return `$${n.toFixed(4)}`;
}

function stepPath(xs: number[], ys: number[], closeY?: number): string {
  if (!xs.length) return "";
  let d = `M ${xs[0]} ${ys[0]}`;
  for (let i = 1; i < xs.length; i++) d += ` H ${xs[i]} V ${ys[i]}`;
  if (closeY != null) d += ` L ${xs[xs.length - 1]} ${closeY} L ${xs[0]} ${closeY} Z`;
  return d;
}

function cumulative(buckets: UsageBucket[]): Pt[] {
  let spend = 0;
  let baseline = 0;
  const nowTs = buckets[buckets.length - 1]?.ts || "";
  return buckets.map((b, i) => {
    spend += Number(b.spend_usd) || 0;
    baseline += Number(b.baseline_usd) || 0;
    const last = i === buckets.length - 1;
    return { ts: b.ts, label: last ? "Now" : ago(b.ts, nowTs), spend, baseline };
  });
}

export function RouterSavingsChart({
  buckets,
  unrealized = false,
}: {
  buckets: UsageBucket[];
  unrealized?: boolean;
}) {
  const points = useMemo((): Pt[] => {
    if (!buckets.length) {
      return [
        { ts: "", label: "1mo ago", spend: 0, baseline: 0 },
        { ts: "", label: "2w ago", spend: 0, baseline: 0 },
        { ts: "", label: "Now", spend: 0.0255, baseline: 0.0503 },
      ];
    }
    return cumulative(buckets);
  }, [buckets]);

  const [hover, setHover] = useState<number | null>(null);
  const n = points.length;
  const max = Math.max(0.05, ...points.map((p) => Math.max(p.spend, p.baseline)));
  const ticks = moneyTicks(max);
  const top = ticks[ticks.length - 1] || 1;
  const xs = points.map((_, i) => (n <= 1 ? L : L + (i / (n - 1)) * (R - L)));
  const yOf = (v: number) => B - (v / top) * (B - T);
  const ysBase = points.map((p) => yOf(p.baseline));
  const ysSpend = points.map((p) => yOf(p.spend));
  const hi = hover == null ? null : Math.max(0, Math.min(n - 1, hover));
  const p = hi == null ? null : points[hi]!;
  const save = p
    ? unrealized
      ? Math.max(0, p.spend - p.baseline)
      : p.baseline > 0
        ? p.baseline - p.spend
        : null
    : null;
  const savePct = p
    ? unrealized
      ? p.spend > 0
        ? (100 * Math.max(0, p.spend - p.baseline)) / p.spend
        : null
      : p.baseline > 0
        ? (100 * (p.baseline - p.spend)) / p.baseline
        : null
    : null;

  function onMove(e: React.MouseEvent<SVGSVGElement> | React.PointerEvent<SVGSVGElement>) {
    const svg = e.currentTarget;
    const r = svg.getBoundingClientRect();
    if (!r.width) return;
    const x = ((e.clientX - r.left) / r.width) * VW;
    const t = (x - L) / (R - L);
    setHover(Math.round(Math.max(0, Math.min(1, t)) * (n - 1)));
  }

  const xLabels = [0, Math.floor((n - 1) / 2), n - 1].filter((i, idx, arr) => arr.indexOf(i) === idx);

  return (
    <Card className="flex flex-col gap-0 rounded-2xl border border-[#1a1a1e] bg-[#08080a] p-6 shadow-xs">
      <CardHeader className="p-0">
        <CardTitle className="flex items-center gap-2 text-[15px] font-semibold text-white">
          <span className="flex size-4 items-center justify-center text-[#8e8e96]">
            <PercentIcon className="size-3.5" />
          </span>
          Router Savings
        </CardTitle>
        <CardDescription className="mt-1 p-0 text-[13px] text-[#71717a]">
          {unrealized
            ? "Cost on AIand org traffic — not your router spend."
            : "Cost on aiand/auto routed traffic only — not your total spend."}
        </CardDescription>
      </CardHeader>
      <CardContent className="relative mt-5 p-0">
        <svg
          viewBox={`0 0 ${VW} ${VH}`}
          width="100%"
          role="img"
          aria-label="Router savings step chart"
          onMouseMove={onMove}
          onPointerMove={onMove}
          onMouseLeave={() => setHover(null)}
          onPointerLeave={() => setHover(null)}
        >
          {/* Y Axis Ticks */}
          <g fontFamily="JetBrains Mono, monospace" fontSize="10" fill="#71717a">
            {ticks.map((t) => (
              <text key={t} x={L - 8} y={yOf(t) + 3} textAnchor="end">
                {axisUsd(t)}
              </text>
            ))}
          </g>

          {/* Grid lines */}
          <g stroke="#18181c" strokeDasharray="3 5" fill="none">
            {ticks.map((t) => (
              <line key={t} x1={L} y1={yOf(t)} x2={R} y2={yOf(t)} />
            ))}
          </g>

          {/* Baseline Area & Line (Dashed grey) */}
          <path d={stepPath(xs, ysBase)} fill="none" stroke={GREY_BASE} strokeWidth="1.6" strokeDasharray="4 4" />

          {/* Routed Spend Line (Solid Blue) */}
          <path
            d={stepPath(xs, ysSpend)}
            fill="none"
            stroke={BLUE_ROUTED}
            strokeWidth="2"
          />

          {/* Hover crosshair & dots */}
          {p && hi != null ? (
            <>
              <line x1={xs[hi]} y1={T} x2={xs[hi]} y2={B} stroke="#ffffff" strokeWidth="1" opacity="0.6" />
              <circle cx={xs[hi]} cy={ysBase[hi]} r="4.5" fill={GREY_BASE} stroke="#000000" strokeWidth="1.5" />
              <circle cx={xs[hi]} cy={ysSpend[hi]} r="4.5" fill={BLUE_ROUTED} stroke="#000000" strokeWidth="1.5" />
            </>
          ) : null}

          {/* X Axis labels */}
          <g fontFamily="JetBrains Mono, monospace" fontSize="10" fill="#71717a">
            {xLabels.map((i) => (
              <text key={`${points[i]!.ts}-${i}`} x={xs[i]} y={236} textAnchor={i === 0 ? "start" : i === n - 1 ? "end" : "middle"}>
                {points[i]!.label}
              </text>
            ))}
          </g>
        </svg>

        {/* Hover Tooltip */}
        {p && hi != null ? (
          <div
            className="pointer-events-none absolute min-w-[200px] max-w-[260px] translate-x-[-50%] translate-y-[-100%] rounded-xl border border-[#27272a] bg-[#0c0c0e] p-3 text-[12px] shadow-2xl z-20"
            style={{
              left: `${Math.min(80, Math.max(20, (xs[hi]! / VW) * 100))}%`,
              top: `${Math.max(10, Math.min(ysBase[hi]!, ysSpend[hi]!) * (100 / VH) - 10)}%`,
            }}
          >
            <div className="mb-2 font-mono text-[11.5px] text-[#8e8e96]">
              {p.ts ? shortTs(p.ts) : p.label}
            </div>
            <div className="flex items-center justify-between gap-4 py-0.5 text-[#8e8e96]">
              <span className="inline-flex items-center gap-1.5">
                <span className="inline-block size-2 rounded-full" style={{ background: GREY_BASE }} />
                Without routing
              </span>
              <span className="font-mono font-medium text-white">{tipUsd(p.baseline)}</span>
            </div>
            <div className="flex items-center justify-between gap-4 py-0.5 text-[#8e8e96]">
              <span className="inline-flex items-center gap-1.5">
                <span className="inline-block size-2 rounded-full" style={{ background: BLUE_ROUTED }} />
                With routing
              </span>
              <span className="font-mono font-medium text-white">{tipUsd(p.spend)}</span>
            </div>
            {save != null && save >= 0 ? (
              <div className="mt-2 border-t border-[#1f1f23] pt-2 font-mono font-medium text-[#4ade80]">
                Saved {tipUsd(save)}
                {savePct != null ? ` (${savePct.toFixed(1)}%)` : ""}
              </div>
            ) : null}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
