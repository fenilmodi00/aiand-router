"use client";

import { useState } from "react";
import { 
  PlayIcon, 
  CheckCircle2Icon, 
  XCircleIcon, 
  SparklesIcon, 
  ArrowRightIcon, 
  SlidersHorizontalIcon,
  LayersIcon,
  ShieldCheckIcon,
  CoinsIcon,
  Code2Icon,
  CpuIcon
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

type Scenario = {
  id: string;
  name: string;
  phase: string;
  complexity: "trivial" | "standard" | "hard" | "frontier";
  prompt: string;
  tokensIn: number;
  tokensOut: number;
  needsTools: boolean;
  toolNames: string[];
};

const PRESET_SCENARIOS: Scenario[] = [
  {
    id: "discovery",
    name: "Repo Discovery & Grep",
    phase: "discover",
    complexity: "trivial",
    prompt: "Grep the codebase for all occurrences of AuthTokenProvider and list their imported file paths.",
    tokensIn: 3200,
    tokensOut: 450,
    needsTools: true,
    toolNames: ["grep_search", "list_dir"],
  },
  {
    id: "unit-test",
    name: "Localized Unit Test Patch",
    phase: "edit",
    complexity: "standard",
    prompt: "Write unit tests for parse_duration in utils.py covering invalid string formats and negative durations.",
    tokensIn: 8400,
    tokensOut: 1200,
    needsTools: true,
    toolNames: ["str_replace", "write_file"],
  },
  {
    id: "multi-file-debug",
    name: "Multi-File Bug Hunt & Refactor",
    phase: "debug",
    complexity: "hard",
    prompt: "Fix race condition between SessionCache eviction worker and WebSocket heartbeat dispatcher across 4 files.",
    tokensIn: 24500,
    tokensOut: 3800,
    needsTools: true,
    toolNames: ["read_file", "apply_patch", "run_command"],
  },
  {
    id: "security-audit",
    name: "Distributed Consensus & Security Audit",
    phase: "security_review",
    complexity: "frontier",
    prompt: "Audit our Raft leader lease renewal against Byzantine fault tolerance corner-cases and propose formal safety guarantees.",
    tokensIn: 48000,
    tokensOut: 6200,
    needsTools: false,
    toolNames: [],
  },
];

type ModelScore = {
  id: string;
  displayName: string;
  inputCost: number;
  outputCost: number;
  pSuccess: number;
  eligible: boolean;
  ineligibleReason?: string;
};

const ALL_MODELS: Omit<ModelScore, "pSuccess" | "eligible">[] = [
  { id: "deepseek-ai/deepseek-v4-flash", displayName: "DeepSeek V4 Flash", inputCost: 0.15, outputCost: 0.25 },
  { id: "google/gemma-4-31b-it", displayName: "Gemma 4 31B", inputCost: 0.20, outputCost: 0.50 },
  { id: "openai/gpt-oss-120b", displayName: "GPT-OSS 120B", inputCost: 0.15, outputCost: 0.60 },
  { id: "qwen/qwen3.6-27b", displayName: "Qwen 3.6 27B", inputCost: 0.32, outputCost: 3.20 },
  { id: "motif-technologies/motif-3", displayName: "Motif-3", inputCost: 0.50, outputCost: 2.00 },
  { id: "moonshotai/kimi-k2.7-code", displayName: "Kimi K2.7 Code", inputCost: 0.75, outputCost: 3.50 },
  { id: "deepseek-ai/deepseek-v4-pro", displayName: "DeepSeek V4 Pro", inputCost: 1.00, outputCost: 2.50 },
  { id: "zai-org/glm-5.2", displayName: "GLM 5.2", inputCost: 1.00, outputCost: 4.00 },
  { id: "moonshotai/kimi-k3", displayName: "Kimi K3 (Frontier)", inputCost: 3.00, outputCost: 12.50 },
];

export function InteractiveRouterSimulator() {
  const [activeScenarioId, setActiveScenarioId] = useState<string>("discovery");
  const [effortTier, setEffortTier] = useState<"low" | "medium" | "high" | "max">("medium");

  const currentScenario = PRESET_SCENARIOS.find((s) => s.id === activeScenarioId) || PRESET_SCENARIOS[0];

  // Knobs per effort tier
  const tierConfig = {
    low: { threshold: 0.05, maxRegret: 0.30 },
    medium: { threshold: 0.10, maxRegret: 0.20 },
    high: { threshold: 0.20, maxRegret: 0.15 },
    max: { threshold: 0.60, maxRegret: 0.03 },
  }[effortTier];

  // Dynamic P(success) simulation per complexity
  const getProbability = (modelId: string, complexity: Scenario["complexity"]): number => {
    const table: Record<string, Record<Scenario["complexity"], number>> = {
      "deepseek-ai/deepseek-v4-flash": { trivial: 0.98, standard: 0.81, hard: 0.54, frontier: 0.28 },
      "google/gemma-4-31b-it": { trivial: 0.96, standard: 0.84, hard: 0.61, frontier: 0.35 },
      "openai/gpt-oss-120b": { trivial: 0.95, standard: 0.86, hard: 0.66, frontier: 0.42 },
      "qwen/qwen3.6-27b": { trivial: 0.97, standard: 0.93, hard: 0.74, frontier: 0.52 },
      "motif-technologies/motif-3": { trivial: 0.96, standard: 0.89, hard: 0.76, frontier: 0.58 },
      "moonshotai/kimi-k2.7-code": { trivial: 0.98, standard: 0.94, hard: 0.88, frontier: 0.68 },
      "deepseek-ai/deepseek-v4-pro": { trivial: 0.99, standard: 0.96, hard: 0.92, frontier: 0.79 },
      "zai-org/glm-5.2": { trivial: 0.99, standard: 0.97, hard: 0.93, frontier: 0.88 },
      "moonshotai/kimi-k3": { trivial: 0.99, standard: 0.99, hard: 0.97, frontier: 0.96 },
    };
    return table[modelId]?.[complexity] ?? 0.8;
  };

  const scoredModels: ModelScore[] = ALL_MODELS.map((m) => {
    const pSuccess = getProbability(m.id, currentScenario.complexity);
    const eligible = true;
    return {
      ...m,
      pSuccess,
      eligible,
    };
  });

  const maxP = Math.max(...scoredModels.map((m) => m.pSuccess));
  const survivors = scoredModels.filter(
    (m) => m.pSuccess >= tierConfig.threshold && (maxP - m.pSuccess) <= tierConfig.maxRegret
  );

  const calcCost = (m: ModelScore) => {
    return (currentScenario.tokensIn / 1_000_000) * m.inputCost + (currentScenario.tokensOut / 1_000_000) * m.outputCost;
  };

  // Sort survivors by total request cost ascending
  survivors.sort((a, b) => calcCost(a) - calcCost(b));
  const winner = survivors[0] || scoredModels[scoredModels.length - 1];

  // Cost vs pure frontier baseline (Kimi K3)
  const frontierBaseline = scoredModels.find((m) => m.id === "moonshotai/kimi-k3") || scoredModels[scoredModels.length - 1];
  const winnerCost = calcCost(winner);
  const baselineCost = calcCost(frontierBaseline);
  const savingsUsd = Math.max(0, baselineCost - winnerCost);
  const savingsPct = baselineCost > 0 ? (savingsUsd / baselineCost) * 100 : 0;

  return (
    <section id="simulator" className="py-16 md:py-24 border-t border-[#1f1f25] bg-[#0c0608]">
      <div className="mx-auto max-w-[1240px] px-6 sm:px-10">
        
        {/* Section Header */}
        <div className="max-w-3xl mb-12">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-[#f2613c]/30 bg-[#f2613c]/10 text-[#f2613c] text-xs font-mono font-medium tracking-wide mb-3">
            INTERACTIVE SIMULATION
          </div>
          <h2 className="text-3xl sm:text-4xl md:text-5xl font-normal tracking-tight text-white leading-tight">
            Watch the Trained ML Router in action.
          </h2>
          <p className="mt-4 text-base text-[#8e8e96] font-light leading-relaxed">
            Select an agent task scenario and effort tier to observe the real-time scoring, 
            Pareto threshold evaluation, and model selection.
          </p>
        </div>

        {/* Preset Selector Tabs */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-8">
          {PRESET_SCENARIOS.map((sc) => {
            const active = sc.id === activeScenarioId;
            return (
              <button
                key={sc.id}
                onClick={() => setActiveScenarioId(sc.id)}
                type="button"
                className={`p-4 rounded-2xl border text-left transition-all flex flex-col justify-between cursor-pointer select-none ${
                  active
                    ? "border-[#f2613c] bg-[#160f11] text-white shadow-lg ring-1 ring-[#f2613c]/40"
                    : "border-[#1f1f25] bg-[#101013] text-neutral-400 hover:border-[#2f2f36] hover:bg-[#141418]"
                }`}
              >
                <div>
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-[10px] uppercase text-[#71717a]">
                      Phase: {sc.phase}
                    </span>
                    <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded ${
                      sc.complexity === "trivial" ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" :
                      sc.complexity === "standard" ? "bg-blue-500/10 text-blue-400 border border-blue-500/20" :
                      sc.complexity === "hard" ? "bg-amber-500/10 text-amber-400 border border-amber-500/20" :
                      "bg-purple-500/10 text-purple-400 border border-purple-500/20"
                    }`}>
                      {sc.complexity}
                    </span>
                  </div>
                  <div className="mt-2 text-sm font-semibold text-white">
                    {sc.name}
                  </div>
                </div>
                <div className="mt-3 text-[11px] font-mono text-[#71717a] flex items-center gap-1.5">
                  <span>{(sc.tokensIn + sc.tokensOut).toLocaleString()} tokens</span>
                  {sc.needsTools ? <span>· {sc.toolNames.length} tools</span> : null}
                </div>
              </button>
            );
          })}
        </div>

        {/* Live Simulator Workspace Box */}
        <div className="rounded-3xl border border-[#232329] bg-[#101013] p-6 lg:p-9 shadow-2xl">
          
          {/* Top Info Bar: Prompt & Context Specs */}
          <div className="grid lg:grid-cols-[1.6fr_1fr] gap-6 pb-6 border-b border-[#1f1f25]">
            <div>
              <span className="text-[11px] font-mono uppercase text-[#71717a] flex items-center gap-1.5 mb-1.5">
                <Code2Icon className="size-3.5 text-[#f2613c]" />
                Input Prompt / Agent Context
              </span>
              <div className="p-3.5 rounded-xl bg-[#0c0608] border border-[#1f1f25] font-mono text-xs text-neutral-200 leading-relaxed min-h-[64px]">
                &ldquo;{currentScenario.prompt}&rdquo;
              </div>
              <div className="mt-2.5 flex flex-wrap items-center gap-2 text-[11px] font-mono text-[#71717a]">
                <span className="bg-[#141417] px-2 py-0.5 rounded border border-[#232329] text-neutral-300">
                  x-agent-phase: {currentScenario.phase}
                </span>
                <span className="bg-[#141417] px-2 py-0.5 rounded border border-[#232329] text-neutral-300">
                  in: {currentScenario.tokensIn.toLocaleString()} tok
                </span>
                <span className="bg-[#141417] px-2 py-0.5 rounded border border-[#232329] text-neutral-300">
                  out: {currentScenario.tokensOut.toLocaleString()} tok
                </span>
                {currentScenario.toolNames.map((t) => (
                  <span key={t} className="bg-[#141417] px-2 py-0.5 rounded border border-[#232329] text-amber-400/90">
                    tool:{t}
                  </span>
                ))}
              </div>
            </div>

            {/* Effort tier control inside simulator */}
            <div className="flex flex-col justify-between p-4 rounded-xl bg-[#0c0608] border border-[#1f1f25]">
              <div>
                <div className="flex items-center justify-between text-xs mb-2">
                  <span className="font-semibold text-white flex items-center gap-1.5">
                    <SlidersHorizontalIcon className="size-3.5 text-[#f2613c]" />
                    Effort Constraint Knobs
                  </span>
                  <span className="font-mono text-[11px] text-[#8e8e96]">
                    Tier: <strong className="text-white uppercase">{effortTier}</strong>
                  </span>
                </div>
                <div className="grid grid-cols-4 gap-1.5 mt-2">
                  {(["low", "medium", "high", "max"] as const).map((t) => (
                    <button
                      key={t}
                      onClick={() => setEffortTier(t)}
                      type="button"
                      className={`py-1.5 rounded-lg text-xs font-mono font-medium transition cursor-pointer select-none ${
                        effortTier === t
                          ? "bg-[#f2613c] text-white font-bold"
                          : "bg-[#141417] text-[#8e8e96] hover:text-white hover:bg-[#1a1a1f]"
                      }`}
                    >
                      {t}
                    </button>
                  ))}
                </div>
              </div>
              <div className="mt-3 pt-3 border-t border-[#1f1f25] flex items-center justify-between font-mono text-[11px]">
                <span className="text-[#8e8e96]">Min Threshold: <strong className="text-[#4ade80] font-bold">{(tierConfig.threshold * 100).toFixed(0)}%</strong></span>
                <span className="text-[#8e8e96]">Max Regret: <strong className="text-amber-400 font-bold">{(tierConfig.maxRegret * 100).toFixed(0)}%</strong></span>
              </div>
            </div>
          </div>

          {/* Scorer Candidate Matrix & Live Decision Breakdown */}
          <div className="mt-6 grid lg:grid-cols-[1.5fr_1fr] gap-8 items-start">
            
            {/* Left: Model Candidate Ranking with Probability Bars */}
            <div>
              <div className="flex items-center justify-between mb-3 text-xs">
                <span className="font-semibold text-white flex items-center gap-1.5">
                  <CpuIcon className="size-3.5 text-neutral-400" />
                  Calibrated Student Scorer Matrix
                </span>
                <span className="font-mono text-[11px] text-[#8e8e96]">
                  Surviving Pareto Pool: <strong className="text-[#4ade80]">{survivors.length}</strong> / 9 models
                </span>
              </div>

              <div className="space-y-2">
                {scoredModels.map((m) => {
                  const isWinner = m.id === winner.id;
                  const isSurvivor = survivors.some((s) => s.id === m.id);
                  const isBaseline = m.id === frontierBaseline.id;
                  const mCost = calcCost(m);
                  const pctWidth = Math.round(m.pSuccess * 100);

                  return (
                    <div
                      key={m.id}
                      className={`p-2.5 rounded-xl border transition-all ${
                        isWinner
                          ? "border-[#4ade80]/60 bg-[#0f1f16] ring-1 ring-[#4ade80]/30"
                          : isSurvivor
                          ? "border-[#1f1f25] bg-[#0c0608]"
                          : "border-[#141418] bg-[#0c0608]/40 opacity-40"
                      }`}
                    >
                      <div className="flex items-center justify-between text-xs mb-1.5">
                        <div className="flex items-center gap-2">
                          <span className={`font-mono text-xs font-semibold ${isWinner ? "text-[#4ade80]" : "text-white"}`}>
                            {m.displayName}
                          </span>
                          {isWinner ? (
                            <Badge className="bg-[#4ade80] text-black text-[10px] font-bold px-1.5 py-0">
                              WINNER (PICK)
                            </Badge>
                          ) : isBaseline ? (
                            <Badge variant="outline" className="border-purple-500/40 text-purple-400 text-[10px] px-1.5 py-0">
                              Frontier Base
                            </Badge>
                          ) : null}
                        </div>
                        <div className="font-mono text-[11px] text-[#8e8e96] flex items-center gap-2">
                          <span>${(mCost).toFixed(4)}/step</span>
                          <span className={`font-bold ${m.pSuccess >= 0.9 ? "text-[#4ade80]" : m.pSuccess >= 0.75 ? "text-amber-400" : "text-neutral-500"}`}>
                            {(m.pSuccess * 100).toFixed(0)}% P(success)
                          </span>
                        </div>
                      </div>

                      {/* Bar Visualizer */}
                      <div className="relative h-1.5 w-full rounded-full bg-[#1c1c22] overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all duration-500 ${
                            isWinner
                              ? "bg-[#4ade80]"
                              : isSurvivor
                              ? "bg-[#71717a]"
                              : "bg-[#27272a]"
                          }`}
                          style={{ width: `${pctWidth}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Right: Decision Header Inspector & Savings Callout */}
            <div className="space-y-4">
              {/* Savings Card */}
              <div className="p-5 rounded-2xl border border-[#4ade80]/40 bg-[#0c1811]">
                <span className="text-[11px] font-mono uppercase text-[#4ade80] flex items-center gap-1.5 font-bold">
                  <CoinsIcon className="size-3.5" />
                  Realized Step Token Savings
                </span>
                <div className="mt-2 flex items-baseline gap-2">
                  <span className="text-3xl font-bold font-mono text-white">
                    {savingsPct.toFixed(1)}%
                  </span>
                  <span className="text-xs text-neutral-300">
                    less than always-frontier
                  </span>
                </div>
                <div className="mt-3 pt-3 border-t border-[#4ade80]/20 text-xs font-mono text-neutral-300 space-y-1">
                  <div className="flex justify-between">
                    <span className="text-[#8e8e96]">AI&amp; Pick Cost:</span>
                    <span className="text-[#4ade80] font-bold">${winnerCost.toFixed(5)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-[#8e8e96]">Frontier Base (K3):</span>
                    <span className="text-[#8e8e96]">${baselineCost.toFixed(5)}</span>
                  </div>
                  <div className="flex justify-between pt-1 border-t border-[#1f1f25]">
                    <span className="text-neutral-300 font-semibold">Net Saved / step:</span>
                    <span className="text-white font-bold">+${savingsUsd.toFixed(5)}</span>
                  </div>
                </div>
              </div>

              {/* Wire Headers Output */}
              <div className="p-4 rounded-xl border border-[#1f1f25] bg-[#0c0608] font-mono text-[11px]">
                <div className="text-[#71717a] uppercase tracking-wider text-[10px] pb-2 border-b border-[#1f1f25] flex items-center justify-between">
                  <span>Ex-Ante Wire Headers</span>
                  <span className="text-[#4ade80]">status: 200 OK</span>
                </div>
                <div className="mt-3 space-y-1 text-neutral-300">
                  <div>
                    <span className="text-[#71717a]">X-Router-Model:</span> <span className="text-[#4ade80] font-bold">{winner.id}</span>
                  </div>
                  <div>
                    <span className="text-[#71717a]">X-Router-Path:</span> <span className="text-white">trained</span>
                  </div>
                  <div>
                    <span className="text-[#71717a]">X-Router-Confidence:</span> <span className="text-amber-400">{(winner.pSuccess).toFixed(3)}</span>
                  </div>
                  <div>
                    <span className="text-[#71717a]">X-Router-Complexity:</span> <span className="text-blue-400">{currentScenario.complexity}</span>
                  </div>
                  <div>
                    <span className="text-[#71717a]">X-Router-Rule:</span> <span className="text-neutral-300">threshold_survivor_cheapest</span>
                  </div>
                  <div>
                    <span className="text-[#71717a]">X-Router-Savings-Usd:</span> <span className="text-[#4ade80]">+${savingsUsd.toFixed(5)}</span>
                  </div>
                </div>
              </div>
            </div>

          </div>

        </div>

      </div>
    </section>
  );
}
