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

export function UsageChart({
  buckets,
  candidates,
}: {
  buckets: UsageBucket[];
  candidates: { id: string }[];
}) {
  const ids = candidates.map((c) => c.id);
  const extra = new Set<string>();
  for (const b of buckets) {
    for (const k of Object.keys(b.by_model || {})) extra.add(k);
  }
  const models = [...ids, ...[...extra].filter((id) => !ids.includes(id))];
  const totals = buckets.map((b) =>
    b.requests ||
    Object.values(b.by_model || {}).reduce((s, n) => s + n, 0),
  );
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

  return (
    <svg viewBox="0 0 560 250" width="100%" role="img" aria-label="Usage bar chart" style={{ marginTop: 6 }}>
      <g fontFamily="JetBrains Mono, monospace" fontSize="10" fill="#71717a">
        {ticks.map((t) => {
          const y = bottom - (t / topTick) * (bottom - top);
          return (
            <text key={t} x="30" y={y + 3} textAnchor="end">
              {t}
            </text>
          );
        })}
      </g>
      <g stroke="#26262b" strokeDasharray="4 5">
        {ticks.map((t) => {
          const y = bottom - (t / topTick) * (bottom - top);
          return <line key={t} x1={left} y1={y} x2="556" y2={y} />;
        })}
      </g>
      {buckets.map((b, i) => {
        const x = left + slot * i + (slot - barW) / 2;
        const parts =
          models.length && Object.keys(b.by_model || {}).length
            ? models
                .map((id, mi) => ({ id, n: b.by_model?.[id] || 0, color: colorFor(id, mi, MIX_COLORS) }))
                .filter((p) => p.n > 0)
            : [{ id: "requests", n: totals[i] || 0, color: MIX_COLORS[2]! }].filter((p) => p.n > 0);
        let y = bottom;
        return parts.map((p, pi) => {
          const h = (p.n / topTick) * (bottom - top);
          y -= h;
          return (
            <rect
              key={`${i}-${p.id}`}
              x={x}
              y={y}
              width={barW}
              height={Math.max(h, 0)}
              fill={p.color}
              rx={pi === parts.length - 1 || pi === 0 ? 2 : 0}
            />
          );
        });
      })}
      <g fontFamily="JetBrains Mono, monospace" fontSize="10" fill="#71717a">
        {buckets.length === 0 ? (
          <text x="298" y="232" textAnchor="middle">
            no hops
          </text>
        ) : (
          buckets.map((b, i) => {
            const show = buckets.length <= 6 || i === 0 || i === buckets.length - 1 || i === Math.floor(buckets.length / 2);
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
  );
}
