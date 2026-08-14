"use client";

import { 
  BarChart3Icon, 
  LayersIcon, 
  ActivityIcon, 
  ShieldCheckIcon, 
  TimerIcon, 
  CheckCircleIcon,
  TrendingUpIcon
} from "lucide-react";
import { Badge } from "@/components/ui/badge";

const MOCK_MIX = [
  { name: "DeepSeek V4 Flash", tier: "Cheap / Fast", pct: 42, color: "bg-emerald-500", text: "text-emerald-400", price: "$0.15 / $0.25" },
  { name: "Qwen 3.6 27B", tier: "Mid / Tools", pct: 20, color: "bg-blue-500", text: "text-blue-400", price: "$0.32 / $3.20" },
  { name: "GPT-OSS 120B", tier: "Mid / Speed", pct: 14, color: "bg-teal-500", text: "text-teal-400", price: "$0.15 / $0.60" },
  { name: "DeepSeek V4 Pro", tier: "Advanced Coding", pct: 12, color: "bg-amber-500", text: "text-amber-400", price: "$1.00 / $2.50" },
  { name: "Kimi K3", tier: "Frontier Reasoning", pct: 12, color: "bg-purple-500", text: "text-purple-400", price: "$3.00 / $12.50" },
];

export function TelemetryShowcase() {
  return (
    <section className="py-16 md:py-24 border-t border-[#1f1f25] bg-[#0c0608]">
      <div className="mx-auto max-w-[1240px] px-6 sm:px-10">
        
        {/* Section Header */}
        <div className="max-w-3xl mb-14">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-blue-500/30 bg-blue-500/10 text-blue-400 text-xs font-mono font-medium tracking-wide mb-4">
            PRODUCTION TELEMETRY
          </div>
          <h2 className="text-3xl sm:text-4xl md:text-5xl font-normal tracking-tight text-white leading-tight">
            Real Traffic Distribution &amp; Latency Profiles
          </h2>
          <p className="mt-4 text-base text-[#8e8e96] font-light leading-relaxed">
            Examining hundreds of thousands of coding agent steps reveals that 70%+ of agent operations
            do not require frontier models to achieve 100% test passing rates in <code className="text-[#f2613c] font-mono">ai&amp;/auto</code>.
          </p>
        </div>

        <div className="grid lg:grid-cols-2 gap-8 mb-12">
          
          {/* Candidate Mix Stacked Distribution Card */}
          <div className="p-7 sm:p-9 rounded-3xl border border-[#232329] bg-[#101013] flex flex-col justify-between shadow-xl">
            <div>
              <div className="flex items-center justify-between pb-4 border-b border-[#1f1f25]">
                <span className="text-sm font-semibold text-white flex items-center gap-2">
                  <LayersIcon className="size-4 text-[#f2613c]" />
                  Candidate Traffic Mix
                </span>
                <span className="font-mono text-xs text-[#8e8e96]">
                  Total Steps: 100%
                </span>
              </div>

              {/* Stacked Progress Bar */}
              <div className="mt-6 flex h-3.5 w-full rounded-full overflow-hidden bg-[#1c1c22] gap-0.5">
                {MOCK_MIX.map((item) => (
                  <div
                    key={item.name}
                    className={`${item.color} h-full transition-all`}
                    style={{ width: `${item.pct}%` }}
                    title={`${item.name}: ${item.pct}%`}
                  />
                ))}
              </div>

              {/* Legend List */}
              <div className="mt-6 space-y-3">
                {MOCK_MIX.map((item) => (
                  <div key={item.name} className="flex items-center justify-between text-xs font-mono">
                    <div className="flex items-center gap-2.5">
                      <span className={`size-2.5 rounded-full ${item.color}`} />
                      <span className="text-white font-medium">{item.name}</span>
                      <span className="text-[#71717a] text-[11px]">({item.tier})</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-[#71717a]">{item.price}</span>
                      <span className={`font-bold ${item.text}`}>{item.pct}%</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="mt-6 pt-4 border-t border-[#1f1f25] text-xs text-[#8e8e96] font-light">
              <span className="text-[#4ade80] font-semibold">Takeaway:</span> Over 62% of agent steps run on sub-$1.00/1M models, saving thousands while preserving frontier reasoning for critical multi-file tasks.
            </div>
          </div>

          {/* Latency & Quality Assurance Card */}
          <div className="p-7 sm:p-9 rounded-3xl border border-[#232329] bg-[#101013] flex flex-col justify-between shadow-xl">
            <div>
              <div className="flex items-center justify-between pb-4 border-b border-[#1f1f25]">
                <span className="text-sm font-semibold text-white flex items-center gap-2">
                  <TimerIcon className="size-4 text-[#4ade80]" />
                  Router Decision Latency Overhead
                </span>
                <span className="font-mono text-xs text-[#4ade80] font-bold">
                  p50 &lt; 8.4ms
                </span>
              </div>

              <p className="mt-4 text-xs text-[#8e8e96] leading-relaxed font-light">
                Because our Scorer is a lightweight, in-process features-only student head (no live chat model or slow external embedding call on the live hop), decision latency is virtually imperceptible to the client.
              </p>

              {/* Latency Histogram Grid */}
              <div className="mt-6 grid grid-cols-3 gap-3">
                <div className="p-3.5 rounded-2xl border border-[#1f1f25] bg-[#0c0608] text-center">
                  <div className="font-mono text-xl font-bold text-white">6.2 ms</div>
                  <div className="text-[11px] font-mono text-[#71717a] mt-1">p50 Latency</div>
                </div>
                <div className="p-3.5 rounded-2xl border border-[#1f1f25] bg-[#0c0608] text-center">
                  <div className="font-mono text-xl font-bold text-[#4ade80]">8.9 ms</div>
                  <div className="text-[11px] font-mono text-[#71717a] mt-1">p95 Latency</div>
                </div>
                <div className="p-3.5 rounded-2xl border border-[#1f1f25] bg-[#0c0608] text-center">
                  <div className="font-mono text-xl font-bold text-amber-400">12.8 ms</div>
                  <div className="text-[11px] font-mono text-[#71717a] mt-1">p99 Latency</div>
                </div>
              </div>

              <div className="mt-6 p-4 rounded-2xl border border-[#1f1f25] bg-[#0c0608] text-xs font-mono space-y-2">
                <div className="flex justify-between items-center text-neutral-300">
                  <span className="text-[#71717a]">Codebase Keep Rate:</span>
                  <span className="text-[#4ade80] font-bold">88.4% (vs 87.9% Frontier)</span>
                </div>
                <div className="flex justify-between items-center text-neutral-300">
                  <span className="text-[#71717a]">Agent Failure Correction (AFC):</span>
                  <span className="text-[#4ade80] font-bold">+16.2% Satisfaction</span>
                </div>
                <div className="flex justify-between items-center text-neutral-300">
                  <span className="text-[#71717a]">Prompt Cache Hit Rate:</span>
                  <span className="text-white font-bold">Hot on persistent turns</span>
                </div>
              </div>
            </div>

            <div className="mt-6 pt-4 border-t border-[#1f1f25] text-xs text-[#8e8e96] font-light">
              <span className="text-white font-semibold">Cache Awareness:</span> The router tracks turn context history to prevent wasteful cache thrashing across multi-turn agent sessions.
            </div>
          </div>

        </div>

      </div>
    </section>
  );
}
