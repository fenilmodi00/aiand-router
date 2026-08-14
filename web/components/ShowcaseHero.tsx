"use client";

import { useState } from "react";
import Link from "next/link";
import { 
  ZapIcon, 
  ArrowRightIcon, 
  TerminalIcon, 
  ActivityIcon, 
  ShieldCheckIcon,
  SparklesIcon,
  ChevronRightIcon
} from "lucide-react";
import { Button } from "@/components/ui/button";

const EFFORT_MODES = [
  {
    id: "low",
    label: "Cost",
    desc: "Optimized for high-volume pipelines & discovery",
    threshold: "P(success) ≥ 0.05",
    regret: "Regret ≤ 0.30",
    savings: "~65% savings",
    tag: "Budget Max",
  },
  {
    id: "medium",
    label: "Balance",
    desc: "Standard daily driver matching top human preference",
    threshold: "P(success) ≥ 0.10",
    regret: "Regret ≤ 0.20",
    savings: "~50% savings",
    tag: "Recommended",
  },
  {
    id: "high",
    label: "Intelligence",
    desc: "Frontier reasoning on complex multi-file tasks",
    threshold: "P(success) ≥ 0.20",
    regret: "Regret ≤ 0.15",
    savings: "~35% savings",
    tag: "Frontier Parity",
  },
  {
    id: "max",
    label: "Max Effort",
    desc: "Unlocks maximum depth and hardest reasoning models",
    threshold: "P(success) ≥ 0.60",
    regret: "Regret ≤ 0.03",
    savings: "Best Output",
    tag: "Ceiling",
  },
];

export function ShowcaseHero() {
  const [selectedEffort, setSelectedEffort] = useState("medium");
  const activeMode = EFFORT_MODES.find((m) => m.id === selectedEffort) || EFFORT_MODES[1];

  return (
    <section className="relative overflow-hidden pt-8 pb-16 md:pt-14 md:pb-24">
      {/* Background ambient glow accents */}
      <div className="pointer-events-none absolute top-0 left-1/2 -translate-x-1/2 -z-10 w-[700px] h-[350px] bg-gradient-to-b from-orange-500/10 via-amber-500/5 to-transparent blur-3xl opacity-60" />
      
      <div className="mx-auto max-w-5xl text-center">
        {/* Top Status Pill */}
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-neutral-800 bg-neutral-900/80 text-xs text-neutral-300 backdrop-blur-md mb-6 shadow-xs">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
          </span>
          <span className="font-mono font-medium text-[11px] tracking-wide text-neutral-200">
            AIAND ML-TRAINED ROUTER v2.4
          </span>
          <span className="text-neutral-600">|</span>
          <span className="text-neutral-400 text-[11px]">Features-Only Scorer &lt;10ms</span>
          <ChevronRightIcon className="size-3 text-neutral-500" />
        </div>

        {/* Main Headline */}
        <h1 className="text-4xl sm:text-5xl md:text-6xl font-semibold tracking-tight text-white leading-[1.12]">
          Intelligent Model Routing for{" "}
          <span className="bg-gradient-to-r from-orange-400 via-amber-300 to-yellow-500 bg-clip-text text-transparent">
            Autonomous Coding Agents
          </span>
        </h1>

        {/* Subtitle */}
        <p className="mt-6 max-w-3xl mx-auto text-base sm:text-lg text-neutral-400 leading-relaxed">
          Stop burning frontier token prices on routine grep, discovery, and localized edits. 
          AIand Router classifies every agent step using a calibrated ML classifier, 
          dispatching the cheapest model that meets your quality bar.
        </p>

        {/* CTA Buttons */}
        <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
          <Button
            render={<a href="#simulator" />}
            nativeButton={false}
            className="h-11 rounded-xl bg-white px-6 text-sm font-semibold text-black hover:bg-neutral-200 shadow-md transition"
          >
            <ZapIcon className="size-4 mr-2 text-orange-600 fill-orange-600" />
            Try Live Simulator
          </Button>

          <Button
            render={<Link href="/playground" />}
            nativeButton={false}
            variant="outline"
            className="h-11 rounded-xl border border-neutral-700 bg-neutral-900/90 px-5 text-sm font-medium text-white hover:bg-neutral-800 transition"
          >
            Open Playground
          </Button>

          <Button
            render={<a href="#integrations" />}
            nativeButton={false}
            variant="outline"
            className="h-11 rounded-xl border border-neutral-800 bg-neutral-950 px-5 text-sm font-mono text-neutral-300 hover:bg-neutral-900 transition"
          >
            <TerminalIcon className="size-4 mr-2 text-neutral-400" />
            model: router/auto
          </Button>
        </div>

        {/* Interactive Optimization Tier Selector */}
        <div className="mt-12 max-w-3xl mx-auto rounded-2xl border border-neutral-800 bg-neutral-950/70 p-4 backdrop-blur-md">
          <div className="flex items-center justify-between px-2 pb-3 text-xs text-neutral-400 border-b border-neutral-800/80">
            <span className="font-mono uppercase tracking-wider text-[11px] text-neutral-400 flex items-center gap-1.5">
              <SparklesIcon className="size-3.5 text-orange-400" />
              Pareto Optimization Modes
            </span>
            <span className="font-mono text-[11px] text-neutral-500">
              Header: <code className="text-neutral-300">x-routing-effort: {selectedEffort}</code>
            </span>
          </div>

          <div className="mt-3 grid grid-cols-2 sm:grid-cols-4 gap-2">
            {EFFORT_MODES.map((mode) => {
              const active = mode.id === selectedEffort;
              return (
                <button
                  key={mode.id}
                  onClick={() => setSelectedEffort(mode.id)}
                  type="button"
                  className={`relative flex flex-col items-start p-3 rounded-xl border text-left transition-all ${
                    active
                      ? "border-orange-500/50 bg-orange-500/10 text-white shadow-sm ring-1 ring-orange-500/30"
                      : "border-neutral-800/80 bg-neutral-900/40 text-neutral-400 hover:border-neutral-700 hover:bg-neutral-900/80"
                  }`}
                >
                  <div className="flex items-center justify-between w-full">
                    <span className={`text-xs font-semibold ${active ? "text-orange-400" : "text-neutral-300"}`}>
                      {mode.label}
                    </span>
                    <span className="text-[10px] font-mono text-neutral-500">
                      {mode.tag}
                    </span>
                  </div>
                  <span className="mt-1 text-[11px] text-neutral-400 line-clamp-1">
                    {mode.savings}
                  </span>
                </button>
              );
            })}
          </div>

          <div className="mt-3.5 px-3 py-2.5 rounded-lg bg-neutral-900/60 border border-neutral-800/60 flex flex-wrap items-center justify-between gap-2 text-xs">
            <div className="text-neutral-300 text-[12px]">
              <span className="font-semibold text-white">{activeMode.label} Mode:</span> {activeMode.desc}
            </div>
            <div className="flex items-center gap-3 font-mono text-[11px] text-neutral-400">
              <span className="text-emerald-400">{activeMode.threshold}</span>
              <span className="text-neutral-600">·</span>
              <span className="text-amber-400">{activeMode.regret}</span>
            </div>
          </div>
        </div>

        {/* 4 Proof Highlights */}
        <div className="mt-14 grid grid-cols-2 md:grid-cols-4 gap-4 max-w-4xl mx-auto text-left">
          <div className="p-4 rounded-xl border border-neutral-800/80 bg-neutral-950/60">
            <div className="text-2xl font-bold font-mono tracking-tight text-emerald-400">40–60%</div>
            <div className="text-xs font-medium text-neutral-200 mt-1">Cost Savings</div>
            <div className="text-[11px] text-neutral-500 mt-0.5">Vs. always-frontier coding baseline</div>
          </div>

          <div className="p-4 rounded-xl border border-neutral-800/80 bg-neutral-950/60">
            <div className="text-2xl font-bold font-mono tracking-tight text-white">&lt;8.4 ms</div>
            <div className="text-xs font-medium text-neutral-200 mt-1">P50 Decision Latency</div>
            <div className="text-[11px] text-neutral-500 mt-0.5">In-process features-only student head</div>
          </div>

          <div className="p-4 rounded-xl border border-neutral-800/80 bg-neutral-950/60">
            <div className="text-2xl font-bold font-mono tracking-tight text-orange-400">99.2%</div>
            <div className="text-xs font-medium text-neutral-200 mt-1">SWE-bench Verified</div>
            <div className="text-[11px] text-neutral-500 mt-0.5">Quality parity with pure frontier</div>
          </div>

          <div className="p-4 rounded-xl border border-neutral-800/80 bg-neutral-950/60">
            <div className="text-2xl font-bold font-mono tracking-tight text-neutral-200">9 Models</div>
            <div className="text-xs font-medium text-neutral-200 mt-1">Single Endpoint</div>
            <div className="text-[11px] text-neutral-500 mt-0.5">Drop-in OpenAI/Anthropic wire format</div>
          </div>
        </div>

      </div>
    </section>
  );
}
