"use client";

import { useState } from "react";
import { 
  CpuIcon, 
  BinaryIcon, 
  GitBranchIcon, 
  BarChart3Icon, 
  ShieldCheckIcon, 
  SparklesIcon, 
  AlertTriangleIcon,
  CheckCircle2Icon,
  LayersIcon,
  DatabaseIcon,
  ActivityIcon,
  TrendingDownIcon
} from "lucide-react";
import { Badge } from "@/components/ui/badge";

export function TrainedVsRulesSection() {
  const [activeTab, setActiveTab] = useState<"pipeline" | "bins" | "calibration">("pipeline");

  return (
    <section className="py-16 md:py-24 border-t border-[#1f1f25] bg-[#0c0608]">
      <div className="mx-auto max-w-[1240px] px-6 sm:px-10">
        
        {/* Section Header */}
        <div className="max-w-3xl mb-14">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-[#f2613c]/30 bg-[#f2613c]/10 text-[#f2613c] text-xs font-mono font-medium tracking-wide mb-4">
            ML ARCHITECTURE DEEP-DIVE
          </div>
          <h2 className="text-3xl sm:text-4xl md:text-5xl font-normal tracking-tight text-white leading-tight">
            Why Trained ML Outperforms Rule-Based Heuristics
          </h2>
          <p className="mt-4 text-base text-[#8e8e96] font-light leading-relaxed">
            Static if-else rules and arbitrary scoring formulas fail when coding agent prompts vary in complexity. 
            Here is how our Student-Teacher distillation and hybrid gold calibration pipeline works in <code className="text-[#f2613c] font-mono">ai&amp;/auto</code>.
          </p>
        </div>

        {/* Side-by-Side Comparison Box */}
        <div className="grid lg:grid-cols-2 gap-6 mb-16">
          
          {/* Rules Card */}
          <div className="p-7 rounded-3xl border border-red-950/40 bg-[#12080a] flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between pb-4 border-b border-red-900/30">
                <span className="font-semibold text-neutral-300 flex items-center gap-2">
                  <AlertTriangleIcon className="size-4 text-red-400" />
                  Brittle Rule-Based Routing
                </span>
                <span className="text-xs font-mono text-red-400 bg-red-950/50 px-2 py-0.5 rounded border border-red-900/50">
                  Legacy Heuristics
                </span>
              </div>
              <ul className="mt-5 space-y-3.5 text-xs text-neutral-400 font-light">
                <li className="flex items-start gap-2.5">
                  <span className="text-red-400 font-bold">✕</span>
                  <span><strong>Arbitrary Linear Weights:</strong> Uses hand-tuned formulas like <code className="text-neutral-300">0.4·AA + 0.2·tools - 0.05·cost</code> that break on edge cases.</span>
                </li>
                <li className="flex items-start gap-2.5">
                  <span className="text-red-400 font-bold">✕</span>
                  <span><strong>Rigid Phase Bars:</strong> Treats all &ldquo;planning&rdquo; steps identically, whether a 1-sentence outline or an enterprise database migration.</span>
                </li>
                <li className="flex items-start gap-2.5">
                  <span className="text-red-400 font-bold">✕</span>
                  <span><strong>Uncalibrated Confidence:</strong> Uses public benchmarks (LMSYS/AA) that do not reflect real agent tool-execution accuracy.</span>
                </li>
                <li className="flex items-start gap-2.5">
                  <span className="text-red-400 font-bold">✕</span>
                  <span><strong>High Retuning Friction:</strong> Adding one new model requires manual recalibration of dozens of interconnected threshold constants.</span>
                </li>
              </ul>
            </div>
            <div className="mt-6 pt-4 border-t border-red-900/30 text-[11px] font-mono text-neutral-500">
              Outcome: Frequent escalations on hard queries or overspending on simple lookups.
            </div>
          </div>

          {/* Trained Card */}
          <div className="p-7 rounded-3xl border border-[#4ade80]/40 bg-[#0c1811] flex flex-col justify-between ring-1 ring-[#4ade80]/20">
            <div>
              <div className="flex items-center justify-between pb-4 border-b border-[#4ade80]/20">
                <span className="font-semibold text-white flex items-center gap-2">
                  <CheckCircle2Icon className="size-4 text-[#4ade80]" />
                  AI&amp; Calibrated ML Router (ai&amp;/auto)
                </span>
                <span className="text-xs font-mono text-[#4ade80] bg-[#14261b] px-2 py-0.5 rounded border border-[#4ade80]/40 font-semibold">
                  Trained ML
                </span>
              </div>
              <ul className="mt-5 space-y-3.5 text-xs text-neutral-300 font-light">
                <li className="flex items-start gap-2.5">
                  <span className="text-[#4ade80] font-bold">✓</span>
                  <span><strong>Query Complexity Binning:</strong> Dissects request features into 4 difficulty tiers (<code className="text-emerald-300">trivial</code>, <code className="text-blue-300">standard</code>, <code className="text-amber-300">hard</code>, <code className="text-purple-300">frontier</code>).</span>
                </li>
                <li className="flex items-start gap-2.5">
                  <span className="text-[#4ade80] font-bold">✓</span>
                  <span><strong>Calibrated P(Success):</strong> In-process student model outputs empirical probabilities calibrated via Platt scaling (<code className="text-emerald-300">ECE ≤ 0.03</code>).</span>
                </li>
                <li className="flex items-start gap-2.5">
                  <span className="text-[#4ade80] font-bold">✓</span>
                  <span><strong>Pareto Optimization:</strong> Automatically finds the lowest list-price unit-cost survivor clearing threshold and max regret.</span>
                </li>
                <li className="flex items-start gap-2.5">
                  <span className="text-[#4ade80] font-bold">✓</span>
                  <span><strong>SWE-bench Verified Gate:</strong> No retrained student head is promoted without verifying ≤1pp quality drop on held-out agent benchmarks.</span>
                </li>
              </ul>
            </div>
            <div className="mt-6 pt-4 border-t border-[#4ade80]/20 text-[11px] font-mono text-[#4ade80] font-medium">
              Outcome: 40–60% token cost reduction with zero observable degradation in completion rates.
            </div>
          </div>

        </div>

        {/* Tab Navigation for Interactive ML Deep-Dive */}
        <div className="flex flex-wrap items-center justify-center gap-2 mb-8">
          <button
            onClick={() => setActiveTab("pipeline")}
            type="button"
            className={`px-4 py-2 rounded-xl text-xs font-mono transition cursor-pointer select-none ${
              activeTab === "pipeline"
                ? "bg-[#f2613c] text-white font-bold shadow"
                : "bg-[#141418] text-[#8e8e96] hover:text-white hover:bg-[#202026]"
            }`}
          >
            4-Stage ML Training Loop
          </button>
          <button
            onClick={() => setActiveTab("bins")}
            type="button"
            className={`px-4 py-2 rounded-xl text-xs font-mono transition cursor-pointer select-none ${
              activeTab === "bins"
                ? "bg-[#f2613c] text-white font-bold shadow"
                : "bg-[#141418] text-[#8e8e96] hover:text-white hover:bg-[#202026]"
            }`}
          >
            Complexity Taxonomy (48 Strata)
          </button>
          <button
            onClick={() => setActiveTab("calibration")}
            type="button"
            className={`px-4 py-2 rounded-xl text-xs font-mono transition cursor-pointer select-none ${
              activeTab === "calibration"
                ? "bg-[#f2613c] text-white font-bold shadow"
                : "bg-[#141418] text-[#8e8e96] hover:text-white hover:bg-[#202026]"
            }`}
          >
            Calibration &amp; Promotion Gate
          </button>
        </div>

        {/* Tab 1: 4-Stage Training Loop */}
        {activeTab === "pipeline" && (
          <div className="grid sm:grid-cols-2 md:grid-cols-4 gap-4">
            <div className="p-6 rounded-3xl border border-[#232329] bg-[#101013] flex flex-col justify-between">
              <div>
                <div className="size-8 rounded-xl bg-[#f2613c]/10 border border-[#f2613c]/30 flex items-center justify-center text-[#f2613c] font-mono text-xs font-bold mb-3">
                  01
                </div>
                <div className="text-sm font-semibold text-white">Teacher Distillation</div>
                <p className="mt-2 text-xs text-[#8e8e96] leading-relaxed font-light">
                  High-tier teachers (Motif-3 with fallback to GLM-5.2) generate silver probability priors and difficulty labels across SWE-smith tool trajectories.
                </p>
              </div>
              <div className="mt-4 pt-3 border-t border-[#1f1f25] text-[11px] font-mono text-[#f2613c]">
                Offline Cheap-then-Escalate
              </div>
            </div>

            <div className="p-6 rounded-3xl border border-[#232329] bg-[#101013] flex flex-col justify-between">
              <div>
                <div className="size-8 rounded-xl bg-blue-500/10 border border-blue-500/30 flex items-center justify-center text-blue-400 font-mono text-xs font-bold mb-3">
                  02
                </div>
                <div className="text-sm font-semibold text-white">Hybrid Gold Matrix</div>
                <p className="mt-2 text-xs text-[#8e8e96] leading-relaxed font-light">
                  Dense Gold Slice (n≥300) runs all models for ground truth. Sparse Gold Train (n=4000) runs 4 anchor models across all 48 strata.
                </p>
              </div>
              <div className="mt-4 pt-3 border-t border-[#1f1f25] text-[11px] font-mono text-blue-400">
                Ground Truth Execution
              </div>
            </div>

            <div className="p-6 rounded-3xl border border-[#232329] bg-[#101013] flex flex-col justify-between">
              <div>
                <div className="size-8 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 font-mono text-xs font-bold mb-3">
                  03
                </div>
                <div className="text-sm font-semibold text-white">Features-Only Scorer</div>
                <p className="mt-2 text-xs text-[#8e8e96] leading-relaxed font-light">
                  In-process logistic/GBDT heads score survivors based on token counts, phase families, and tool schemas with under 10ms decision overhead.
                </p>
              </div>
              <div className="mt-4 pt-3 border-t border-[#1f1f25] text-[11px] font-mono text-emerald-400">
                &lt;10ms In-Process Serve
              </div>
            </div>

            <div className="p-6 rounded-3xl border border-[#232329] bg-[#101013] flex flex-col justify-between">
              <div>
                <div className="size-8 rounded-xl bg-purple-500/10 border border-purple-500/30 flex items-center justify-center text-purple-400 font-mono text-xs font-bold mb-3">
                  04
                </div>
                <div className="text-sm font-semibold text-white">Shadow &amp; Gate</div>
                <p className="mt-2 text-xs text-[#8e8e96] leading-relaxed font-light">
                  Every student head runs in shadow mode and must beat the rules baseline on SWE-bench Verified (500 tasks) before live promotion.
                </p>
              </div>
              <div className="mt-4 pt-3 border-t border-[#1f1f25] text-[11px] font-mono text-purple-400">
                SWE-bench Verified Gate
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: Complexity Taxonomy */}
        {activeTab === "bins" && (
          <div className="p-7 rounded-3xl border border-[#232329] bg-[#101013]">
            <div className="mb-4 text-xs text-[#8e8e96]">
              Our classifier partitions incoming agent steps into 4 distinct difficulty boundaries across 6 Phase Families (<code className="text-neutral-300">discover</code>, <code className="text-neutral-300">plan</code>, <code className="text-neutral-300">edit</code>, <code className="text-neutral-300">tool</code>, <code className="text-neutral-300">debug</code>, <code className="text-neutral-300">summarize</code>) and tools presence (48 sampling cells):
            </div>
            <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="p-4 rounded-2xl border border-emerald-500/20 bg-[#0d1a12]">
                <span className="font-mono text-xs font-bold text-emerald-400 uppercase">trivial (15%)</span>
                <p className="mt-1.5 text-xs text-neutral-300 font-light">One-shot grep, rename, format, comments, docstring generation, lookup.</p>
                <div className="mt-3 font-mono text-[11px] text-[#71717a]">Typical Pick: Flash ($0.15/1M)</div>
              </div>
              <div className="p-4 rounded-2xl border border-blue-500/20 bg-[#0d1622]">
                <span className="font-mono text-xs font-bold text-blue-400 uppercase">standard (40%)</span>
                <p className="mt-1.5 text-xs text-neutral-300 font-light">Localized function implement, unit test fix, structured tool call with clear spec.</p>
                <div className="mt-3 font-mono text-[11px] text-[#71717a]">Typical Pick: Qwen 3.6 / GPT-OSS</div>
              </div>
              <div className="p-4 rounded-2xl border border-amber-500/20 bg-[#21160a]">
                <span className="font-mono text-xs font-bold text-amber-400 uppercase">hard (30%)</span>
                <p className="mt-1.5 text-xs text-neutral-300 font-light">Multi-file refactor, debug-after-failure, security review, cross-cutting plan.</p>
                <div className="mt-3 font-mono text-[11px] text-[#71717a]">Typical Pick: DeepSeek Pro / Kimi 2.7</div>
              </div>
              <div className="p-4 rounded-2xl border border-purple-500/20 bg-[#1c0f24]">
                <span className="font-mono text-xs font-bold text-purple-400 uppercase">frontier (15%)</span>
                <p className="mt-1.5 text-xs text-neutral-300 font-light">Novel algorithm, massive ambiguous repo, SWE-Verified class, adversarial logic.</p>
                <div className="mt-3 font-mono text-[11px] text-[#71717a]">Typical Pick: Kimi K3 / GLM-5.2</div>
              </div>
            </div>
          </div>
        )}

        {/* Tab 3: Calibration & Promotion */}
        {activeTab === "calibration" && (
          <div className="grid md:grid-cols-2 gap-6 p-7 rounded-3xl border border-[#232329] bg-[#101013]">
            <div>
              <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                <ActivityIcon className="size-4 text-emerald-400" />
                Calibrated Probabilities (ECE ≤ 0.03)
              </h3>
              <p className="mt-2 text-xs text-[#8e8e96] leading-relaxed font-light">
                Raw classifier confidence scores are uncalibrated. We apply Platt scaling and temperature adjustment over the held-out dense gold slice so that predicted success probabilities match empirical execution outcomes.
              </p>
              <div className="mt-4 p-3.5 rounded-2xl bg-[#0c0608] border border-[#1f1f25] font-mono text-xs text-neutral-300 space-y-1.5">
                <div className="flex justify-between">
                  <span className="text-[#71717a]">Brier Skill Score (BSS):</span>
                  <span className="text-emerald-400 font-bold">&gt; 0.0 (Strict Skill)</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#71717a]">Expected Calibration Error:</span>
                  <span className="text-emerald-400 font-bold">ECE ≤ 0.03</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#71717a]">Calibration Method:</span>
                  <span className="text-white">Platt (n&lt;1000) / Isotonic</span>
                </div>
              </div>
            </div>

            <div>
              <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                <ShieldCheckIcon className="size-4 text-purple-400" />
                SWE-bench Verified Promotion Bar
              </h3>
              <p className="mt-2 text-xs text-[#8e8e96] leading-relaxed font-light">
                Every newly trained Scorer artifact is validated against the 500-instance SWE-bench Verified benchmark in shadow mode before handling live developer requests.
              </p>
              <div className="mt-4 p-3.5 rounded-2xl bg-[#0c0608] border border-[#1f1f25] font-mono text-xs text-neutral-300 space-y-1.5">
                <div className="flex justify-between">
                  <span className="text-[#71717a]">Quality Parity:</span>
                  <span className="text-emerald-400 font-bold">≥ Rules - 1.0 pp</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#71717a]">Realized Cost Delta:</span>
                  <span className="text-emerald-400 font-bold">&lt; $0.00 (Strictly Lower)</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#71717a]">Drift Canary:</span>
                  <span className="text-white">Trips retrain on 7d / n≥300 drift</span>
                </div>
              </div>
            </div>
          </div>
        )}

      </div>
    </section>
  );
}
