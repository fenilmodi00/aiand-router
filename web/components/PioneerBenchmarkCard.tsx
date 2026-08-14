"use client";

import { CheckCircle2Icon, TrendingDownIcon, SparklesIcon, AwardIcon } from "lucide-react";
import { Badge } from "@/components/ui/badge";

export function PioneerBenchmarkCard() {
  const BENCHMARKS = [
    {
      model: "Always Claude Opus 4.8 / K3",
      costPerTask: "$0.0094",
      relativeCost: 100,
      resolveRate: "52.4%",
      color: "bg-neutral-600",
      textColor: "text-neutral-400",
      highlight: false,
    },
    {
      model: "Always GPT-5.5 / Pro",
      costPerTask: "$0.0077",
      relativeCost: 82,
      resolveRate: "49.8%",
      color: "bg-neutral-600",
      textColor: "text-neutral-400",
      highlight: false,
    },
    {
      model: "Always Kimi K2.7 Code",
      costPerTask: "$0.0045",
      relativeCost: 48,
      resolveRate: "44.2%",
      color: "bg-neutral-600",
      textColor: "text-neutral-400",
      highlight: false,
    },
    {
      model: "AI& Model Router (ai&/auto)",
      costPerTask: "$0.0036",
      relativeCost: 38,
      resolveRate: "52.6%",
      color: "bg-[#f2613c]",
      textColor: "text-[#f2613c]",
      highlight: true,
    },
  ];

  return (
    <section id="benchmarks" className="py-16 md:py-24 border-t border-[#1f1f25] bg-[#0c0608]">
      <div className="mx-auto max-w-[1240px] px-6 sm:px-10">
        
        {/* Section Header */}
        <div className="max-w-3xl mb-12">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-[#f2613c]/30 bg-[#f2613c]/10 text-[#f2613c] text-xs font-mono font-medium tracking-wide mb-4">
            BENCHMARKS
          </div>
          <h2 className="text-3xl sm:text-4xl md:text-5xl font-normal tracking-tight text-white leading-tight">
            Frontier quality at a fraction of the cost.
          </h2>
          <p className="mt-4 text-base text-[#8e8e96] font-light leading-relaxed">
            AI&amp; Router (<code className="text-[#f2613c] font-mono">ai&amp;/auto</code>) vs. always-Opus / K3 — Preliminary results on SWE-Bench Verified (June 2026).
            Cost measured as average cost per solved task across real coding agent traces.
          </p>
        </div>

        {/* Benchmark Visualizer Card */}
        <div className="rounded-3xl border border-[#232329] bg-[#101013] p-6 sm:p-10 shadow-2xl">
          
          <div className="flex flex-wrap items-center justify-between pb-6 border-b border-[#1f1f25] gap-4">
            <div>
              <span className="font-mono text-xs text-[#71717a] uppercase">BENCHMARK METRIC</span>
              <div className="text-lg font-semibold text-white mt-0.5">SWE-Bench Verified (500 Instances)</div>
            </div>
            <div className="flex items-center gap-6 font-mono text-xs text-[#8e8e96]">
              <div>Baseline: <span className="text-white">$0.0094 / task</span></div>
              <div className="text-[#4ade80] font-bold">62% Cost Reduction</div>
            </div>
          </div>

          {/* Benchmark Bars Comparison */}
          <div className="mt-8 space-y-5">
            {BENCHMARKS.map((item) => (
              <div
                key={item.model}
                className={`p-4 rounded-2xl border transition-all ${
                  item.highlight
                    ? "border-[#f2613c]/50 bg-[#160f11] ring-1 ring-[#f2613c]/30"
                    : "border-[#1f1f25] bg-[#0c0608]"
                }`}
              >
                <div className="flex flex-wrap items-center justify-between gap-2 text-xs font-mono mb-2.5">
                  <div className="flex items-center gap-2.5">
                    <span className={`font-semibold text-sm ${item.highlight ? "text-white" : "text-[#8e8e96]"}`}>
                      {item.model}
                    </span>
                    {item.highlight ? (
                      <span className="px-2 py-0.5 rounded-full bg-[#f2613c] text-white text-[10px] font-bold">
                        AI&amp; AUTO
                      </span>
                    ) : null}
                  </div>
                  <div className="flex items-center gap-4 text-xs">
                    <span className="text-[#71717a]">Pass Rate: <strong className="text-white">{item.resolveRate}</strong></span>
                    <span className={`font-bold ${item.highlight ? "text-[#4ade80]" : "text-white"}`}>
                      {item.costPerTask} / task ({item.relativeCost}%)
                    </span>
                  </div>
                </div>

                {/* Progress bar */}
                <div className="relative h-3 w-full rounded-full bg-[#1a1a20] overflow-hidden">
                  <div
                    className={`h-full rounded-full transition-all duration-700 ${item.color}`}
                    style={{ width: `${item.relativeCost}%` }}
                  />
                </div>
              </div>
            ))}
          </div>

          {/* Bottom Callout */}
          <div className="mt-8 p-4 rounded-2xl bg-[#0c0608] border border-[#1f1f25] flex flex-col sm:flex-row sm:items-center justify-between gap-4 text-xs font-mono text-[#8e8e96]">
            <div>
              <strong className="text-white">Why it works:</strong> Routine discovery, greps, and local unit test patches are routed to ultra-fast $0.15/1M models, saving full reasoning capacity for hard multi-file problems.
            </div>
            <div className="text-[#4ade80] font-bold shrink-0">
              Zero Loss in Resolve Rate
            </div>
          </div>

        </div>

      </div>
    </section>
  );
}
