"use client";

import { useState } from "react";
import { 
  CalculatorIcon, 
  TrendingDownIcon, 
  SparklesIcon, 
  DollarSignIcon, 
  UsersIcon, 
  ZapIcon,
  CheckIcon
} from "lucide-react";
import { Badge } from "@/components/ui/badge";

export function RoiCalculator() {
  const [devs, setDevs] = useState<number>(20);
  const [requestsPerDay, setRequestsPerDay] = useState<number>(60);
  const [avgTokens, setAvgTokens] = useState<number>(14000);
  const [baselineModelRate, setBaselineModelRate] = useState<"frontier" | "mid">("frontier");

  // Calculations
  const workingDaysPerMonth = 22;
  const monthlyRequests = devs * requestsPerDay * workingDaysPerMonth;
  const monthlyTokensInMillion = (monthlyRequests * avgTokens) / 1_000_000;

  // Blended cost per 1M tokens:
  // Frontier Baseline (Opus 4.8 / K3 tier): $6.80 blended ($3 in, $12.50 out at 40/60 mix)
  // Mid-tier Baseline (GPT-5.6 Sol / Daily driver): $3.80 blended
  const baselineRatePer1M = baselineModelRate === "frontier" ? 6.80 : 3.80;
  
  // AI& Router Blended Cost per 1M:
  // Dynamically routes: 45% Flash ($0.21), 35% Mid ($1.80), 20% Frontier ($6.80) = ~$2.08 blended
  const routedRatePer1M = baselineModelRate === "frontier" ? 2.08 : 1.62;

  const monthlyBaselineCost = monthlyTokensInMillion * baselineRatePer1M;
  const monthlyRoutedCost = monthlyTokensInMillion * routedRatePer1M;
  const monthlySavings = Math.max(0, monthlyBaselineCost - monthlyRoutedCost);
  const annualSavings = monthlySavings * 12;
  const savingsPct = monthlyBaselineCost > 0 ? (monthlySavings / monthlyBaselineCost) * 100 : 0;

  return (
    <section className="py-16 md:py-24 border-t border-[#1f1f25] bg-[#0c0608]">
      <div className="mx-auto max-w-[1240px] px-6 sm:px-10">
        
        {/* Section Header */}
        <div className="max-w-3xl mb-14">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-[#f2613c]/30 bg-[#f2613c]/10 text-[#f2613c] text-xs font-mono font-medium tracking-wide mb-4">
            TOKEN ECONOMICS CALCULATOR
          </div>
          <h2 className="text-3xl sm:text-4xl md:text-5xl font-normal tracking-tight text-white leading-tight">
            Calculate Your Team&apos;s Annual AI Savings
          </h2>
          <p className="mt-4 text-base text-[#8e8e96] font-light leading-relaxed">
            Adjust team size, daily agent steps, and context volume to see the real dollar difference
            between unrouted frontier spend and <code className="text-[#f2613c] font-mono">ai&amp;/auto</code> dynamic Pareto routing.
          </p>
        </div>

        <div className="grid lg:grid-cols-[1.2fr_1fr] gap-8 items-center rounded-3xl border border-[#232329] bg-[#101013] p-6 sm:p-10 shadow-2xl">
          
          {/* Left: Interactive Controls */}
          <div className="space-y-6">
            
            {/* Control 1: Dev Count */}
            <div>
              <div className="flex items-center justify-between text-xs mb-2">
                <span className="font-semibold text-white flex items-center gap-1.5">
                  <UsersIcon className="size-3.5 text-[#8e8e96]" />
                  Active Engineers / Coding Agents
                </span>
                <span className="font-mono text-sm font-bold text-[#f2613c]">
                  {devs} devs
                </span>
              </div>
              <input
                type="range"
                min="1"
                max="200"
                value={devs}
                onChange={(e) => setDevs(Number(e.target.value))}
                className="w-full h-2 bg-[#1f1f25] rounded-lg appearance-none cursor-pointer accent-[#f2613c]"
              />
              <div className="flex justify-between text-[10px] font-mono text-[#71717a] mt-1">
                <span>1 dev</span>
                <span>50 devs</span>
                <span>100 devs</span>
                <span>200 devs</span>
              </div>
            </div>

            {/* Control 2: Steps per dev */}
            <div>
              <div className="flex items-center justify-between text-xs mb-2">
                <span className="font-semibold text-white flex items-center gap-1.5">
                  <ZapIcon className="size-3.5 text-[#8e8e96]" />
                  Agent Steps / Prompts per Dev / Day
                </span>
                <span className="font-mono text-sm font-bold text-[#f2613c]">
                  {requestsPerDay} steps/day
                </span>
              </div>
              <input
                type="range"
                min="10"
                max="250"
                step="5"
                value={requestsPerDay}
                onChange={(e) => setRequestsPerDay(Number(e.target.value))}
                className="w-full h-2 bg-[#1f1f25] rounded-lg appearance-none cursor-pointer accent-[#f2613c]"
              />
              <div className="flex justify-between text-[10px] font-mono text-[#71717a] mt-1">
                <span>10 steps</span>
                <span>100 steps</span>
                <span>250 steps</span>
              </div>
            </div>

            {/* Control 3: Avg tokens per step */}
            <div>
              <div className="flex items-center justify-between text-xs mb-2">
                <span className="font-semibold text-white flex items-center gap-1.5">
                  <CalculatorIcon className="size-3.5 text-[#8e8e96]" />
                  Average Context Length per Request
                </span>
                <span className="font-mono text-sm font-bold text-[#f2613c]">
                  {(avgTokens / 1000).toFixed(0)}k tokens
                </span>
              </div>
              <input
                type="range"
                min="2000"
                max="64000"
                step="2000"
                value={avgTokens}
                onChange={(e) => setAvgTokens(Number(e.target.value))}
                className="w-full h-2 bg-[#1f1f25] rounded-lg appearance-none cursor-pointer accent-[#f2613c]"
              />
              <div className="flex justify-between text-[10px] font-mono text-[#71717a] mt-1">
                <span>2k</span>
                <span>16k</span>
                <span>32k</span>
                <span>64k tokens</span>
              </div>
            </div>

            {/* Control 4: Baseline model selector */}
            <div>
              <span className="text-xs font-semibold text-white block mb-2">
                Comparison Baseline Strategy
              </span>
              <div className="grid grid-cols-2 gap-2">
                <button
                  type="button"
                  onClick={() => setBaselineModelRate("frontier")}
                  className={`p-3.5 rounded-2xl border text-left transition cursor-pointer select-none ${
                    baselineModelRate === "frontier"
                      ? "border-[#f2613c] bg-[#1a0f12] text-white ring-1 ring-[#f2613c]/40"
                      : "border-[#1f1f25] bg-[#0c0608] text-[#8e8e96] hover:text-white hover:bg-[#141418]"
                  }`}
                >
                  <div className="text-xs font-semibold">100% Frontier Driver</div>
                  <div className="text-[11px] text-[#71717a] mt-0.5">Opus 4.8 / K3 / Fable 5 (~$6.80/1M)</div>
                </button>
                <button
                  type="button"
                  onClick={() => setBaselineModelRate("mid")}
                  className={`p-3.5 rounded-2xl border text-left transition cursor-pointer select-none ${
                    baselineModelRate === "mid"
                      ? "border-[#f2613c] bg-[#1a0f12] text-white ring-1 ring-[#f2613c]/40"
                      : "border-[#1f1f25] bg-[#0c0608] text-[#8e8e96] hover:text-white hover:bg-[#141418]"
                  }`}
                >
                  <div className="text-xs font-semibold">Mid-Tier Daily Driver</div>
                  <div className="text-[11px] text-[#71717a] mt-0.5">GPT-5.6 Sol / Kimi 2.7 (~$3.80/1M)</div>
                </button>
              </div>
            </div>

          </div>

          {/* Right: Projected Savings Output Card */}
          <div className="p-7 sm:p-9 rounded-3xl border border-[#4ade80]/40 bg-[#0c1811] flex flex-col justify-between">
            <div>
              <span className="font-mono text-xs uppercase tracking-wider text-[#4ade80] flex items-center gap-1.5 font-semibold">
                <TrendingDownIcon className="size-4" />
                Projected Annual Savings
              </span>

              <div className="mt-3 text-4xl sm:text-5xl font-extrabold font-mono tracking-tight text-white">
                ${Math.round(annualSavings).toLocaleString()}
                <span className="text-sm font-normal text-[#8e8e96] ml-1">/ year</span>
              </div>

              <div className="mt-2 inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-[#14261b] border border-[#4ade80]/30 text-[#4ade80] text-xs font-mono font-semibold">
                <span>{savingsPct.toFixed(0)}% Net Cost Reduction</span>
              </div>

              <div className="mt-6 pt-6 border-t border-[#4ade80]/20 space-y-3 text-xs font-mono">
                <div className="flex justify-between text-neutral-300">
                  <span className="text-[#8e8e96]">Monthly Agent Traffic:</span>
                  <span className="font-bold">{monthlyRequests.toLocaleString()} steps ({monthlyTokensInMillion.toFixed(1)}M tok)</span>
                </div>
                <div className="flex justify-between text-neutral-300">
                  <span className="text-[#8e8e96]">Unrouted Baseline Spend:</span>
                  <span className="text-red-400">${Math.round(monthlyBaselineCost).toLocaleString()} / mo</span>
                </div>
                <div className="flex justify-between text-neutral-300">
                  <span className="text-[#8e8e96]">AI&amp; Routed Spend (ai&amp;/auto):</span>
                  <span className="text-[#4ade80] font-bold">${Math.round(monthlyRoutedCost).toLocaleString()} / mo</span>
                </div>
                <div className="flex justify-between pt-2 border-t border-[#1f1f25] text-white font-bold text-sm">
                  <span>Monthly Savings:</span>
                  <span className="text-[#4ade80]">+${Math.round(monthlySavings).toLocaleString()} / mo</span>
                </div>
              </div>
            </div>

            <div className="mt-8 pt-4 border-t border-[#1f1f25] text-[11px] text-[#8e8e96]">
              <span className="text-white font-medium">Zero Code Change:</span> Point OpenCode, Claude Code, or Cursor at <code className="text-[#f2613c]">http://127.0.0.1:8000/v1</code> with <code className="text-[#f2613c]">model: ai&amp;/auto</code>.
            </div>
          </div>

        </div>

      </div>
    </section>
  );
}
