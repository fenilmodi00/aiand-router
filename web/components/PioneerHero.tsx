"use client";

import { useState } from "react";
import Link from "next/link";
import { 
  ArrowRightIcon, 
  SparklesIcon, 
  TerminalIcon, 
  CheckIcon, 
  ZapIcon, 
  SlidersIcon,
  LayersIcon,
  CpuIcon,
  CheckCircle2Icon
} from "lucide-react";
import { Button } from "@/components/ui/button";

type PreviewItem = {
  phase: string;
  name: string;
  complexity: "trivial" | "standard" | "hard" | "frontier";
  prompt: string;
  tokens: string;
  chosen: string;
  chosenCost: string;
  baselineCost: string;
  savings: string;
  confidence: string;
  candidates: {
    name: string;
    prob: number;
    cost: string;
    status: "winner" | "eligible" | "below-bar" | "baseline";
  }[];
};

const ROUTER_PREVIEWS: PreviewItem[] = [
  {
    phase: "discover",
    name: "Repo Discovery & Grep",
    complexity: "trivial",
    prompt: "Grep auth tokens across 12 files and summarize public API endpoint routes.",
    tokens: "3.2k tok",
    chosen: "deepseek-ai/deepseek-v4-flash",
    chosenCost: "$0.0006",
    baselineCost: "$0.0240",
    savings: "97.5%",
    confidence: "98.2%",
    candidates: [
      { name: "DeepSeek V4 Flash", prob: 98, cost: "$0.15 / $0.25", status: "winner" },
      { name: "Gemma 4 31B", prob: 95, cost: "$0.20 / $0.50", status: "eligible" },
      { name: "GPT-OSS 120B", prob: 94, cost: "$0.15 / $0.60", status: "eligible" },
      { name: "Qwen 3.6 27B", prob: 96, cost: "$0.32 / $3.20", status: "eligible" },
      { name: "DeepSeek V4 Pro", prob: 99, cost: "$1.00 / $2.50", status: "eligible" },
      { name: "Kimi K3 (Frontier)", prob: 99, cost: "$3.00 / $12.50", status: "baseline" },
    ],
  },
  {
    phase: "plan",
    name: "Architecture & Multi-Step Plan",
    complexity: "standard",
    prompt: "Plan migration from REST polling to bidirectional WebSocket heartbeat streaming.",
    tokens: "12.5k tok",
    chosen: "openai/gpt-oss-120b",
    chosenCost: "$0.0031",
    baselineCost: "$0.0450",
    savings: "93.1%",
    confidence: "94.8%",
    candidates: [
      { name: "DeepSeek V4 Flash", prob: 82, cost: "$0.15 / $0.25", status: "below-bar" },
      { name: "GPT-OSS 120B", prob: 94, cost: "$0.15 / $0.60", status: "winner" },
      { name: "Qwen 3.6 27B", prob: 95, cost: "$0.32 / $3.20", status: "eligible" },
      { name: "DeepSeek V4 Pro", prob: 97, cost: "$1.00 / $2.50", status: "eligible" },
      { name: "Kimi K3 (Frontier)", prob: 98, cost: "$3.00 / $12.50", status: "baseline" },
    ],
  },
  {
    phase: "edit",
    name: "Localized Implementation & Patch",
    complexity: "standard",
    prompt: "Refactor parse_duration in utils.py and fix boundary edge cases for negative inputs.",
    tokens: "8.4k tok",
    chosen: "qwen/qwen3.6-27b",
    chosenCost: "$0.0042",
    baselineCost: "$0.0480",
    savings: "91.2%",
    confidence: "93.4%",
    candidates: [
      { name: "DeepSeek V4 Flash", prob: 78, cost: "$0.15 / $0.25", status: "below-bar" },
      { name: "Qwen 3.6 27B", prob: 93, cost: "$0.32 / $3.20", status: "winner" },
      { name: "Kimi K2.7 Code", prob: 95, cost: "$0.75 / $3.50", status: "eligible" },
      { name: "DeepSeek V4 Pro", prob: 96, cost: "$1.00 / $2.50", status: "eligible" },
      { name: "Kimi K3 (Frontier)", prob: 98, cost: "$3.00 / $12.50", status: "baseline" },
    ],
  },
  {
    phase: "debug",
    name: "Multi-File Bug Hunt & Race Condition",
    complexity: "hard",
    prompt: "Trace multi-threaded race condition in SessionCache eviction across 4 source modules.",
    tokens: "26.0k tok",
    chosen: "deepseek-ai/deepseek-v4-pro",
    chosenCost: "$0.0340",
    baselineCost: "$0.1620",
    savings: "79.0%",
    confidence: "92.0%",
    candidates: [
      { name: "DeepSeek V4 Flash", prob: 48, cost: "$0.15 / $0.25", status: "below-bar" },
      { name: "Qwen 3.6 27B", prob: 72, cost: "$0.32 / $3.20", status: "below-bar" },
      { name: "Kimi K2.7 Code", prob: 89, cost: "$0.75 / $3.50", status: "eligible" },
      { name: "DeepSeek V4 Pro", prob: 92, cost: "$1.00 / $2.50", status: "winner" },
      { name: "Kimi K3 (Frontier)", prob: 97, cost: "$3.00 / $12.50", status: "baseline" },
    ],
  },
  {
    phase: "security_review",
    name: "Cryptographic & Security Audit",
    complexity: "frontier",
    prompt: "Audit Raft leader lease renewal against Byzantine split-brain network partition attacks.",
    tokens: "48.0k tok",
    chosen: "moonshotai/kimi-k3",
    chosenCost: "$0.2850",
    baselineCost: "$0.2850",
    savings: "Frontier Pick",
    confidence: "96.4%",
    candidates: [
      { name: "DeepSeek V4 Flash", prob: 28, cost: "$0.15 / $0.25", status: "below-bar" },
      { name: "Qwen 3.6 27B", prob: 52, cost: "$0.32 / $3.20", status: "below-bar" },
      { name: "DeepSeek V4 Pro", prob: 79, cost: "$1.00 / $2.50", status: "below-bar" },
      { name: "GLM 5.2", prob: 88, cost: "$1.00 / $4.00", status: "eligible" },
      { name: "Kimi K3 (Frontier)", prob: 96, cost: "$3.00 / $12.50", status: "winner" },
    ],
  },
  {
    phase: "summarize",
    name: "PR & Final Code Summary",
    complexity: "trivial",
    prompt: "Generate concise pull request release notes and breaking changes summary for v2.4.",
    tokens: "4.5k tok",
    chosen: "google/gemma-4-31b-it",
    chosenCost: "$0.0011",
    baselineCost: "$0.0290",
    savings: "96.2%",
    confidence: "96.0%",
    candidates: [
      { name: "DeepSeek V4 Flash", prob: 94, cost: "$0.15 / $0.25", status: "eligible" },
      { name: "Gemma 4 31B", prob: 96, cost: "$0.20 / $0.50", status: "winner" },
      { name: "GPT-OSS 120B", prob: 95, cost: "$0.15 / $0.60", status: "eligible" },
      { name: "Qwen 3.6 27B", prob: 97, cost: "$0.32 / $3.20", status: "eligible" },
      { name: "Kimi K3 (Frontier)", prob: 99, cost: "$3.00 / $12.50", status: "baseline" },
    ],
  },
];

export function PioneerHero() {
  const [activeTab, setActiveTab] = useState<number>(0);
  const active = ROUTER_PREVIEWS[activeTab] || ROUTER_PREVIEWS[0];

  return (
    <section className="relative pt-10 pb-20 md:pt-16 md:pb-28 overflow-hidden">
      
      {/* Background ambient lighting */}
      <div className="pointer-events-none absolute top-10 left-1/2 -translate-x-1/2 -z-10 w-[800px] h-[400px] bg-gradient-to-b from-[#f2613c]/15 via-[#ea580c]/5 to-transparent blur-[120px]" />

      <div className="mx-auto max-w-[1240px] px-6 sm:px-10">
        
        {/* Top Header & Copy */}
        <div className="max-w-3xl">
          {/* Badge */}
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-[#f2613c]/30 bg-[#f2613c]/10 text-[#f2613c] text-xs font-mono font-medium tracking-wide mb-6">
            <span className="size-1.5 rounded-full bg-[#f2613c] animate-pulse" />
            AI&amp; MODEL ROUTER · ai&amp;/auto
          </div>

          {/* Headline */}
          <h1 className="text-4xl sm:text-5xl md:text-6xl font-normal tracking-tight text-white leading-[1.1]">
            Every task gets exactly the model it needs.
          </h1>

          {/* Subtitle */}
          <p className="mt-6 text-base sm:text-lg text-[#8e8e96] leading-relaxed font-light">
            AI&amp; model router (<code className="text-[#f2613c] font-mono">ai&amp;/auto</code>) sits in front of your model pool. 
            For each incoming request, it predicts the probability that each candidate model will succeed. 
            Then it picks the cheapest one that clears your confidence threshold.
          </p>

          {/* CTAs */}
          <div className="mt-8 flex flex-wrap items-center gap-4">
            <Button
              render={<Link href="/playground" />}
              nativeButton={false}
              className="h-11 rounded-full bg-white px-7 text-xs font-semibold text-black hover:bg-neutral-200 transition shadow-sm cursor-pointer"
            >
              Get started →
            </Button>
            <Button
              render={<a href="#how-it-works" />}
              nativeButton={false}
              variant="outline"
              className="h-11 rounded-full border-[#27272a] bg-[#101013] px-6 text-xs font-medium text-neutral-300 hover:bg-[#1a1a1e] hover:text-white transition cursor-pointer"
            >
              How it works ↗
            </Button>
          </div>
        </div>

        {/* Live Pioneer-Style Interactive Routing Diagram Card */}
        <div className="mt-14 rounded-3xl border border-[#232329] bg-[#0c0608] p-6 sm:p-9 shadow-2xl relative z-10">
          
          {/* Scenario Tab Selector Buttons */}
          <div className="flex flex-wrap items-center justify-between gap-3 pb-6 border-b border-[#1f1f25]">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs font-mono uppercase text-[#71717a]">Select Agent Step:</span>
              <div className="flex flex-wrap items-center gap-1.5 p-1 rounded-xl bg-[#141417] border border-[#232329]">
                {ROUTER_PREVIEWS.map((item, idx) => {
                  const isCurrent = activeTab === idx;
                  return (
                    <button
                      key={item.phase}
                      onClick={() => setActiveTab(idx)}
                      type="button"
                      className={`px-3 py-1.5 rounded-lg text-xs font-mono transition cursor-pointer select-none ${
                        isCurrent
                          ? "bg-[#f2613c] text-white font-bold shadow-xs"
                          : "text-[#8e8e96] hover:text-white hover:bg-[#202025]"
                      }`}
                    >
                      phase: {item.phase}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="flex items-center gap-3 font-mono text-xs text-[#8e8e96]">
              <span>Complexity: <strong className="text-[#f2613c] uppercase">{active.complexity}</strong></span>
              <span className="text-[#3f3f46]">·</span>
              <span>Model Pool: <strong className="text-white">9 Models</strong></span>
            </div>
          </div>

          {/* Interactive Flow Grid: Request -> Router -> Candidate Models */}
          <div className="mt-8 grid lg:grid-cols-[1.1fr_auto_1.6fr] gap-6 items-center">
            
            {/* 1. Request Box */}
            <div className="p-5 rounded-2xl border border-[#1f1f25] bg-[#101013] flex flex-col justify-between h-full">
              <div>
                <div className="flex items-center justify-between text-xs font-mono text-[#71717a] pb-3 border-b border-[#1f1f25]">
                  <span>REQUEST</span>
                  <span className="text-[#f2613c] font-bold">model: ai&amp;/auto</span>
                </div>
                <div className="mt-3.5 p-3.5 rounded-xl bg-[#0c0608] border border-[#1a1a1e] font-mono text-xs text-neutral-200 leading-relaxed min-h-[72px]">
                  &ldquo;{active.prompt}&rdquo;
                </div>
              </div>
              <div className="mt-4 pt-3 border-t border-[#1a1a1e] flex items-center justify-between font-mono text-[11px] text-[#71717a]">
                <span>Phase: <strong className="text-white">{active.phase}</strong></span>
                <span>Context: <strong className="text-white">{active.tokens}</strong></span>
              </div>
            </div>

            {/* Middle Router Arrow / Score Pill */}
            <div className="hidden lg:flex flex-col items-center justify-center px-2 text-center">
              <div className="size-12 rounded-2xl bg-[#1a1416] border border-[#f2613c]/40 flex items-center justify-center text-[#f2613c] shadow-lg shadow-[#f2613c]/10 animate-pulse">
                <CpuIcon className="size-5" />
              </div>
              <span className="mt-2 font-mono text-[10px] text-[#f2613c] uppercase font-bold tracking-wider">
                SCORE &amp; ROUTE
              </span>
              <span className="text-[10px] font-mono text-[#71717a]">&lt;8.4ms p50</span>
            </div>

            {/* 2. Candidate Models Scored List */}
            <div className="space-y-2">
              <div className="flex items-center justify-between text-xs font-mono text-[#71717a] px-1 pb-1">
                <span>CANDIDATE SURVIVORS</span>
                <span>P(SUCCESS) · LIST PRICE</span>
              </div>

              {active.candidates.map((c) => {
                const isWinner = c.status === "winner";
                const isBelow = c.status === "below-bar";
                const isBase = c.status === "baseline";

                return (
                  <div
                    key={c.name}
                    className={`p-3 rounded-xl border transition-all ${
                      isWinner
                        ? "border-[#4ade80]/60 bg-[#0f1f16] ring-1 ring-[#4ade80]/40"
                        : isBelow
                        ? "border-[#1f1f25]/50 bg-[#0c0608] opacity-40"
                        : "border-[#1f1f25] bg-[#101013]"
                    }`}
                  >
                    <div className="flex items-center justify-between text-xs mb-1.5">
                      <div className="flex items-center gap-2">
                        <span className={`font-mono text-xs ${isWinner ? "font-bold text-[#4ade80]" : "text-neutral-200"}`}>
                          {c.name}
                        </span>
                        {isWinner ? (
                          <span className="px-1.5 py-0.5 rounded bg-[#4ade80] text-black font-mono font-bold text-[9px]">
                            PICK · CHEAPEST ABOVE BAR
                          </span>
                        ) : isBase ? (
                          <span className="px-1.5 py-0.5 rounded bg-[#2b2225] text-[#f2613c] font-mono text-[9px]">
                            FRONTIER BASE
                          </span>
                        ) : null}
                      </div>
                      <div className="font-mono text-[11px] flex items-center gap-3">
                        <span className="text-[#71717a]">{c.cost}</span>
                        <span className={`font-bold ${isWinner ? "text-[#4ade80]" : isBelow ? "text-neutral-500" : "text-white"}`}>
                          {c.prob}%
                        </span>
                      </div>
                    </div>

                    {/* Progress Probability bar */}
                    <div className="relative h-1.5 w-full rounded-full bg-[#1c1c22] overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all duration-500 ${
                          isWinner
                            ? "bg-[#4ade80]"
                            : isBelow
                            ? "bg-neutral-600"
                            : "bg-[#71717a]"
                        }`}
                        style={{ width: `${c.prob}%` }}
                      />
                    </div>
                  </div>
                );
              })}

              {/* Step Result Banner */}
              <div className="mt-4 p-3 rounded-xl bg-[#141012] border border-[#f2613c]/30 flex items-center justify-between text-xs font-mono text-neutral-300">
                <div>
                  Dispatched: <strong className="text-white">{active.chosen}</strong> ({active.chosenCost})
                </div>
                <div className="text-[#4ade80] font-bold">
                  {active.savings} {active.savings.includes("Pick") ? "" : "savings vs always-Opus/K3"}
                </div>
              </div>

            </div>

          </div>

        </div>

      </div>
    </section>
  );
}
