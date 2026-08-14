"use client";

import { useState } from "react";
import { MIX_COLORS, type UsageBucket } from "@/lib/types";
import { colorFor, shortTs } from "@/lib/format";

function niceTicks(max: number): number[] {
  const cap = Math.max(1, max);
  let step = 1;
  if (cap > 4) step = 5;
  if (cap > 20) step = 20;
  if (cap > 80) step = 50;
  if (cap > 200) step = 100;
  if (cap > 500) step = 200;
  const out: number[] = [];
  for (let v = 0; v <= cap + 1e-9; v += step) out.push(v);
  if (out[out.length - 1]! < cap) out.push(out[out.length - 1]! + step);
  if (out.length < 2) out.push(step);
  return out;
}

function modelLabel(id: string, candidates: { id: string; display_name?: string }[]): string {
  const hit = candidates.find((c) => c.id === id);
  if (hit?.display_name) return hit.display_name;
  return (id.split("/").pop() || id).replace(/-/g, " ");
}

export function UsageChart({
  buckets,
  candidates,
}: {
  buckets: UsageBucket[];
  candidates: { id: string; display_name?: string }[];
}) {
  const [hover, setHover] = useState<number | null>(null);
  const ids = candidates.map((c) => c.id);
  const extra = new Set<string>();
  for (const b of buckets) {
    for (const k of Object.keys(b.by_model || {})) extra.add(k);
  }
  const models = [...ids, ...[...extra].filter((id) => !ids.includes(id))];
  const partsFor = (b: UsageBucket, i: number) => {
    const mix = b.by_model || {};
    if (models.length && Object.keys(mix).length) {
      return models
        .map((id, mi) => ({ id, n: mix[id] || 0, color: colorFor(id, mi, MIX_COLORS) }))
        .filter((p) => p.n > 0);
    }
    const n = b.requests || 0;
    return n > 0 ? [{ id: "requests", n, color: MIX_COLORS[2]! }] : [];
  };
  const totals = buckets.map((b, i) => partsFor(b, i).reduce((s, p) => s + p.n, 0));
  const max = Math.max(0, ...totals);
  const ticks = niceTicks(max);
  const topTick = ticks[ticks.length - 1] || 1;
  const left = 40;
  const right = 556;
  const top = 10;
  const bottom = 210;
  const n = Math.max(buckets.length, 1);
  const slot = (right - left) / n;
  const barW = Math.min(34, Math.max(10, slot - 10));
  const hi = hover == null ? null : Math.max(0, Math.min(buckets.length - 1, hover));
  const tip = hi == null ? null : buckets[hi];
  const tipParts = hi == null ? [] : partsFor(buckets[hi]!, hi);

  return (
    <div className="relative">
      <svg
        viewBox="0 0 560 250"
        width="100%"
        role="img"
        aria-label="Usage bar chart"
        style={{ marginTop: 6 }}
        onMouseLeave={() => setHover(null)}
        onPointerLeave={() => setHover(null)}
      >
        <g fontFamily="JetBrains Mono, monospace" fontSize="10" fill="var(--muted-foreground)">
          {ticks.map((t) => {
            const y = bottom - (t / topTick) * (bottom - top);
            return (
              <text key={t} x="30" y={y + 3} textAnchor="end">
                {t}
              </text>
            );
          })}
        </g>
        <g stroke="var(--border)" strokeDasharray="4 5">
          {ticks.map((t) => {
            const y = bottom - (t / topTick) * (bottom - top);
            return <line key={t} x1={left} y1={y} x2="556" y2={y} />;
          })}
        </g>
        {buckets.map((b, i) => {
          const x = left + slot * i + (slot - barW) / 2;
          const parts = partsFor(b, i);
          let y = bottom;
          return (
            <g key={`${b.ts}-${i}`} opacity={hi == null || hi === i ? 1 : 0.45}>
              {parts.map((p, pi) => {
                const h = (p.n / topTick) * (bottom - top);
                y -= h;
                return (
                  <rect
                    key={p.id}
                    x={x}
                    y={y}
                    width={barW}
                    height={Math.max(h, 0)}
                    fill={p.color}
                    rx={pi === parts.length - 1 || pi === 0 ? 2 : 0}
                  />
                );
              })}
              <rect
                x={left + slot * i}
                y={top}
                width={slot}
                height={bottom - top}
                fill="transparent"
                onMouseEnter={() => setHover(i)}
                onPointerEnter={() => setHover(i)}
              />
            </g>
          );
        })}
        <g fontFamily="JetBrains Mono, monospace" fontSize="10" fill="var(--muted-foreground)">
          {buckets.length === 0 ? (
            <text x="298" y="232" textAnchor="middle">
              no hops
            </text>
          ) : (
            buckets.map((b, i) => {
              const show =
                buckets.length <= 6 ||
                i === 0 ||
                i === buckets.length - 1 ||
                i === Math.floor(buckets.length / 2);
              if (!show) return null;
              return (
                <text key={b.ts} x={left + slot * i + slot / 2} y="232" textAnchor="middle">
                  {shortTs(b.ts)}
                </text>
              );
            })
          )}
        </g>
      </svg>
      {tip && tipParts.length ? (
        <div
          className="pointer-events-none absolute z-10 min-w-44 max-w-65 translate-x-[-8px] rounded-[10px] border border-border bg-popover p-2.5 text-[12.5px] shadow-lg"
          style={{
            left: `${Math.min(72, Math.max(4, ((left + slot * hi! + slot / 2) / 560) * 100))}%`,
            top: `${Math.max(8, ((bottom - (totals[hi!]! / topTick) * (bottom - top)) / 250) * 100 - 8)}%`,
          }}
        >
          <div className="mb-2 font-semibold">{shortTs(tip.ts)}</div>
          {tipParts.map((p) => (
            <div key={p.id} className="mt-1 flex items-center justify-between gap-4.5 text-muted-foreground">
              <span className="inline-flex items-center">
                <span className="mr-1.5 inline-block size-2 rounded-[2px]" style={{ background: p.color }} />
                {p.id === "requests" ? "Requests" : modelLabel(p.id, candidates)}
              </span>
              <b className="font-mono text-xs font-medium text-foreground">{p.n}</b>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}
