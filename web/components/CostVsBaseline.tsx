import { usd, pct } from "@/lib/format";
import type { UsageBucket } from "@/lib/types";

/**
 * Pioneer-style "Cost vs. baseline" simple meter card.
 * Shows routed spend vs baseline (most expensive candidate) with meters.
 */
function totalUsd(buckets: UsageBucket[], key: "spend_usd" | "baseline_usd"): number {
  return buckets.reduce((s, b) => s + Number(b[key] || 0), 0);
}

export function CostVsBaseline({
  buckets,
  savingsUsd,
  savingsPct,
  unrealized = false,
}: {
  buckets: UsageBucket[];
  savingsUsd: number;
  savingsPct: number;
  unrealized?: boolean;
}) {
  const routed = totalUsd(buckets, "spend_usd");
  const baseline = totalUsd(buckets, "baseline_usd");
  const max = Math.max(routed, baseline, 1);
  const routedPct = (routed / max) * 100;
  const baselinePct = (baseline / max) * 100;
  const saved =
    savingsUsd > 0
      ? savingsUsd
      : unrealized
        ? Math.max(0, routed - baseline)
        : Math.max(0, baseline - routed);

  return (
    <div className="flex flex-col gap-0 rounded-2xl border border-[#1a1a1e] bg-[#08080a] p-6 shadow-xs">
      <div className="text-[15px] font-semibold text-white">Cost vs. baseline</div>
      <div className="mt-1 text-[13px] text-[#71717a]">
        {unrealized
          ? "What you spent vs Flash (default medium pick)."
          : "Routed cost against always routing to the most expensive candidate."}
      </div>

      <div className="mt-5">
        <div className="flex items-center justify-between text-[13px]">
          <span className="font-medium text-white">{unrealized ? "Spent (actual)" : "Routed (actual)"}</span>
          <span className="font-mono text-[12.5px] text-white">{usd(routed)}</span>
        </div>
        <div className="mt-2 h-[5px] w-full rounded-full bg-[#18181c] overflow-hidden">
          <div
            className="h-full rounded-full bg-[#4ade80] transition-all"
            style={{ width: `${Math.min(100, routedPct)}%` }}
          />
        </div>
      </div>

      <div className="mt-5">
        <div className="flex items-center justify-between text-[13px]">
          <span className="text-[#71717a]">
            {unrealized ? "Baseline (Flash)" : "Baseline (most expensive)"}
          </span>
          <span className="font-mono text-[12.5px] text-[#71717a]">{usd(baseline)}</span>
        </div>
        <div className="mt-2 h-[5px] w-full rounded-full bg-[#18181c] overflow-hidden">
          <div
            className="h-full rounded-full bg-[#27272a] transition-all"
            style={{ width: `${Math.min(100, baselinePct)}%` }}
          />
        </div>
      </div>

      <div className="mt-5 text-[13px] text-[#71717a]">
        {saved > 0 ? (
          <>
            {unrealized ? "Could save" : "Saved"}{" "}
            <span className="font-mono text-[12.5px] text-[#4ade80] font-medium">{usd(saved)}</span>
            {savingsPct > 0 ? (
              <> ({pct(savingsPct)})</>
            ) : baseline > 0 ? (
              <> ({pct((saved / baseline) * 100)})</>
            ) : null}
            {unrealized ? " by routing through router/auto" : ""} this period.
          </>
        ) : (
          <>
            {unrealized ? "No savings" : "Saved"}{" "}
            <span className="font-mono text-[12.5px] text-[#4ade80] font-medium">{usd(0)}</span> (0.0%) this period.
          </>
        )}
      </div>
    </div>
  );
}
