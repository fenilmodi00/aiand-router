"use client";

import { useMemo, useState } from "react";
import type { UsageBucket } from "@/lib/types";

const VW = 720;
const VH = 248;
const L = 56;
const R = 708;
const T = 10;
const B = 214;
const BASE = "#a8b0bc";
const ORANGE = "#f2613c";

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
  const raw = (max > 0 ? max : 1) * 1.15;
  const pow = 10 ** Math.floor(Math.log10(raw));
  const n = raw / pow;
  const nice = n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10;
  const top = nice * pow;
  const step = top / 4;
  return [0, step, 2 * step, 3 * step, top];
}

function axisUsd(n: number): string {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(n);
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

export function RouterSavingsChart({ buckets }: { buckets: UsageBucket[] }) {
  const points = useMemo((): Pt[] => {
    if (!buckets.length) {
      return [
        { ts: "", label: "—", spend: 0, baseline: 0 },
        { ts: "", label: "Now", spend: 0, baseline: 0 },
      ];
    }
    return cumulative(buckets);
  }, [buckets]);
  const [hover, setHover] = useState<number | null>(null);
  const n = points.length;
  const max = Math.max(0, ...points.map((p) => Math.max(p.spend, p.baseline)));
  const ticks = moneyTicks(max);
  const top = ticks[ticks.length - 1] || 1;
  const xs = points.map((_, i) => (n <= 1 ? L : L + (i / (n - 1)) * (R - L)));
  const yOf = (v: number) => B - (v / top) * (B - T);
  const ysBase = points.map((p) => yOf(p.baseline));
  const ysSpend = points.map((p) => yOf(p.spend));
  const hi = hover == null ? null : Math.max(0, Math.min(n - 1, hover));
  const p = hi == null ? null : points[hi]!;
  const save = p && p.baseline > 0 ? p.baseline - p.spend : null;
  const savePct = p && p.baseline > 0 ? (100 * (p.baseline - p.spend)) / p.baseline : null;

  function onMove(e: { currentTarget: SVGSVGElement; clientX: number }) {
    const svg = e.currentTarget;
    const r = svg.getBoundingClientRect();
    if (!r.width) return;
    const x = ((e.clientX - r.left) / r.width) * VW;
    const t = (x - L) / (R - L);
    setHover(Math.round(Math.max(0, Math.min(1, t)) * (n - 1)));
  }

  const xLabels = [0, Math.floor((n - 1) / 2), n - 1].filter((i, idx, arr) => arr.indexOf(i) === idx);

  return (
    <>
      <div className="savings-head">
        <div className="card-title">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
            <path d="M10 13a5 5 0 0 0 7.54.54l1.42-1.42a5 5 0 0 0-7.07-7.07L10.5 6.3" />
            <path d="M14 11a5 5 0 0 0-7.54-.54L5.04 11.88a5 5 0 0 0 7.07 7.07L13.5 17.7" />
          </svg>
          Router Savings
        </div>
        <span className="est-pill">estimated</span>
      </div>
      <p className="card-sub">
        Estimated savings versus always routing to the most expensive eligible candidate — not your
        total org spend.
      </p>
      <div className="savings-plot">
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
          <g fontFamily="JetBrains Mono, monospace" fontSize="10" fill="#71717a">
            {ticks.map((t) => (
              <text key={t} x={L - 8} y={yOf(t) + 3} textAnchor="end">
                {axisUsd(t)}
              </text>
            ))}
          </g>
          <g stroke="#2a2a32" strokeDasharray="3 5" fill="none">
            {ticks.map((t) => (
              <line key={t} x1={L} y1={yOf(t)} x2={R} y2={yOf(t)} />
            ))}
          </g>
          <path d={stepPath(xs, ysBase, B)} fill={BASE} fillOpacity="0.14" stroke="none" />
          <path d={stepPath(xs, ysBase)} fill="none" stroke={BASE} strokeWidth="1.6" />
          <path
            d={stepPath(xs, ysSpend)}
            fill="none"
            stroke={ORANGE}
            strokeWidth="1.7"
            strokeDasharray="3.5 4"
          />
          {p && hi != null ? (
            <>
              <line x1={xs[hi]} y1={T} x2={xs[hi]} y2={B} stroke="#fafafa" strokeWidth="1" />
              <circle cx={xs[hi]} cy={ysBase[hi]} r="4" fill={BASE} stroke="#0a0a0b" strokeWidth="1" />
              <circle cx={xs[hi]} cy={ysSpend[hi]} r="4" fill={ORANGE} stroke="#0a0a0b" strokeWidth="1" />
            </>
          ) : null}
          <g fontFamily="JetBrains Mono, monospace" fontSize="10" fill="#71717a">
            {xLabels.map((i) => (
              <text key={`${points[i]!.ts}-${i}`} x={xs[i]} y={236} textAnchor="middle">
                {points[i]!.label}
              </text>
            ))}
          </g>
        </svg>
        {p && hi != null ? (
          <div
            className="savings-tip"
            style={{
              left: `${Math.min(72, Math.max(4, (xs[hi]! / VW) * 100))}%`,
              top: `${Math.min(ysBase[hi]!, ysSpend[hi]!) * (100 / VH)}%`,
            }}
          >
            <div className="h">{p.label}</div>
            <div className="row">
              <span>
                <span className="dot" style={{ background: BASE }} />
                Your spend
              </span>
              <b>{tipUsd(p.baseline)}</b>
            </div>
            <div className="row">
              <span>
                <span className="dot" style={{ background: ORANGE }} />
                With router (est.)
              </span>
              <b>{tipUsd(p.spend)}</b>
            </div>
            {save != null && savePct != null && save >= 0 ? (
              <div className="foot">
                Could save {tipUsd(save)} ({savePct.toFixed(1)}%) · est.
              </div>
            ) : null}
          </div>
        ) : null}
      </div>
    </>
  );
}
