"use client";

import Link from "next/link";
import { 
  CpuIcon, 
  ShieldCheckIcon, 
  TerminalIcon, 
  ArrowRightIcon, 
  ZapIcon, 
  LayersIcon,
  CheckCircle2Icon
} from "lucide-react";

export function PioneerFeaturePillars() {
  const PILLARS = [
    {
      num: "01",
      title: "SCORE EVERY REQUEST",
      tagline: "Calibrated multi-candidate scoring in under 10ms.",
      description: "AI&'s in-process features-only student head evaluates task complexity, phase family, and tool schemas, outputting calibrated empirical P(success) probabilities for each candidate.",
      features: [
        "In-process features-only student classifier (<8.4ms p50)",
        "No chat model or slow embedding API calls on live hop",
        "Calibrated with Platt scaling & temperature adjustment (ECE ≤ 0.03)",
        "Trained on 48 strata across SWE-smith tool trajectories",
      ],
      linkText: "Explore the ML Scorer ↗",
      href: "#architecture",
    },
    {
      num: "02",
      title: "CLEAR YOUR CONFIDENCE BAR",
      tagline: "Cheapest model that meets your quality bar.",
      description: "You define where you sit on the cost-intelligence Pareto frontier. The router drops models that fall below your threshold or lag the top candidate by more than max-regret.",
      features: [
        "4 Effort Tiers: Cost (low), Balance (medium), Intelligence (high), Max",
        "Regret-bounded survivor pool prevents catastrophic task failure",
        "Dynamic token pricing engine ranks list-price unit costs",
        "Fallback gracefully to rules baseline if scorer ever degrades",
      ],
      linkText: "View effort tiers ↗",
      href: "#simulator",
    },
    {
      num: "03",
      title: "ONE UNIVERSAL ENDPOINT",
      tagline: "Drop-in wire compatibility with zero lock-in.",
      description: "A single OpenAI-compatible base URL. Send model: ai&/auto from OpenCode, Claude Code, Cursor, Codex, or Python SDK without rewriting your agent harnesses.",
      features: [
        "Drop-in /v1/chat/completions endpoint",
        "Full streaming, tool calling, and JSON schema output support",
        "Ex-ante decision headers (X-Router-Model, Confidence, Savings)",
        "Persistent prompt-cache aware routing to prevent cache thrashing",
      ],
      linkText: "View integration guides ↗",
      href: "#integrations",
    },
  ];

  return (
    <section id="how-it-works" className="py-20 md:py-28 border-t border-[#1f1f25] bg-[#0c0608]">
      <div className="mx-auto max-w-[1240px] px-6 sm:px-10">
        
        {/* Section Title */}
        <div className="max-w-3xl mb-16">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-[#f2613c]/30 bg-[#f2613c]/10 text-[#f2613c] text-xs font-mono font-medium tracking-wide mb-4">
            HOW IT WORKS
          </div>
          <h2 className="text-3xl sm:text-4xl md:text-5xl font-normal tracking-tight text-white leading-tight">
            Built for developers who care about both quality and spend.
          </h2>
          <p className="mt-4 text-base text-[#8e8e96] font-light leading-relaxed">
            Everything your inference stack needs to scale agentic coding workloads efficiently with <code className="text-[#f2613c] font-mono">ai&amp;/auto</code>.
          </p>
        </div>

        {/* 3 Pillar Cards Grid */}
        <div className="grid md:grid-cols-3 gap-6">
          {PILLARS.map((p) => (
            <div
              key={p.num}
              className="p-7 sm:p-8 rounded-3xl border border-[#232329] bg-[#101013] flex flex-col justify-between hover:border-[#f2613c]/40 transition duration-300 group"
            >
              <div>
                {/* Number & Title */}
                <div className="flex items-baseline gap-3">
                  <span className="font-mono text-xl font-bold text-[#f2613c]">
                    {p.num}
                  </span>
                  <span className="font-mono text-xs uppercase tracking-wider text-[#8e8e96]">
                    {p.title}
                  </span>
                </div>

                {/* Tagline */}
                <h3 className="mt-4 text-lg font-semibold text-white group-hover:text-[#f2613c] transition">
                  {p.tagline}
                </h3>

                {/* Description */}
                <p className="mt-3 text-xs sm:text-[13px] text-[#8e8e96] leading-relaxed font-light">
                  {p.description}
                </p>

                {/* Bullet Points */}
                <ul className="mt-6 space-y-2.5 text-xs text-neutral-300 font-light border-t border-[#1f1f25] pt-5">
                  {p.features.map((feat) => (
                    <li key={feat} className="flex items-start gap-2">
                      <span className="text-[#f2613c] text-xs">·</span>
                      <span className="leading-snug">{feat}</span>
                    </li>
                  ))}
                </ul>
              </div>

              {/* Link */}
              <div className="mt-8 pt-4 border-t border-[#1f1f25]">
                <a
                  href={p.href}
                  className="inline-flex items-center text-xs font-mono font-medium text-white hover:text-[#f2613c] transition"
                >
                  {p.linkText}
                </a>
              </div>
            </div>
          ))}
        </div>

      </div>
    </section>
  );
}
