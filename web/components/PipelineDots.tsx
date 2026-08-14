"use client";

import { useEffect, useRef } from "react";

export function PipelineDots({
  colors,
  counts,
}: {
  colors: string[];
  counts: number[];
}) {
  const ref = useRef<SVGGElement>(null);
  const n = colors.length;
  const liveN = counts.filter((c) => c > 0).length;
  const nDots = liveN ? Math.min(Math.max(liveN, 3), 5) : 2;

  useEffect(() => {
    const root = ref.current;
    const svg = root?.ownerSVGElement;
    if (!root || !svg) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const inbound = svg.querySelector<SVGPathElement>("#rp-in");
    if (!inbound) return;
    const outs = Array.from({ length: n }, (_, i) =>
      svg.querySelector<SVGPathElement>(`#rp-m-${i}`),
    );
    if (outs.some((p) => !p)) return;

    const live = counts
      .map((c, i) => (c > 0 ? i : -1))
      .filter((i) => i >= 0)
      .sort((a, b) => counts[b]! - counts[a]!);
    const roster = live.length ? live : colors.map((_, i) => i);
    const hop = live.length ? 1800 : 2600;
    const period = hop * 2;
    const stagger = live.length ? hop * 0.55 : hop;
    const inLen = inbound.getTotalLength();
    const outLen = outs.map((p) => p!.getTotalLength());
    const dots = [...root.querySelectorAll("circle")];

    let raf = 0;
    const t0 = performance.now();
    const tick = (now: number) => {
      for (let d = 0; d < dots.length; d++) {
        const t = now - t0 + d * stagger;
        const model = live.length
          ? roster[d % roster.length]!
          : roster[Math.floor(t / period) % roster.length]!;
        const local = ((t % period) + period) % period;
        const onIn = local < hop;
        const path = onIn ? inbound : outs[model]!;
        const len = onIn ? inLen : outLen[model]!;
        const pt = path.getPointAtLength((onIn ? local / hop : (local - hop) / hop) * len);
        const c = dots[d]!;
        c.setAttribute("cx", String(pt.x));
        c.setAttribute("cy", String(pt.y));
        c.setAttribute("fill", onIn ? "var(--orange)" : colors[model]!);
        c.setAttribute("opacity", "0.9");
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [colors, counts, n]);

  return (
    <g ref={ref} aria-hidden="true">
      {Array.from({ length: nDots }, (_, i) => (
        <circle key={i} r="4.5" opacity="0" />
      ))}
    </g>
  );
}
