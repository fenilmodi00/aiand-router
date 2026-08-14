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
    <div className="card card-pad flex flex-col gap-0 rounded-[14px] border border-[#232329] bg-[#101013] p-[22px_24px]">
      <div className="text-[15px] font-semibold">Cost vs. baseline</div>
      <div className="mt-1 text-[13px] text-[#8e8e96]">
        {unrealized
          ? "What you spent vs Flash (default medium pick)."
          : "Routed cost against always routing to the most expensive candidate."}
      </div>

      <div className="mt-5">
        <div className="flex items-center justify-between text-[13px]">
          <span>{unrealized ? "Spent (actual)" : "Routed (actual)"}</span>
          <span className="font-mono text-[12.5px] text-[#fafafa]">{usd(routed)}</span>
        </div>
        <div className="mt-[9px] h-[6px] rounded-[3px] bg-[#26262b]">
          <div
            className="h-full rounded-[3px] bg-[#4ade80] transition-all"
            style={{ width: `${Math.min(100, routedPct)}%` }}
          />
        </div>
      </div>

      <div className="mt-5">
        <div className="flex items-center justify-between text-[13px]">
          <span className="text-[#8e8e96]">
            {unrealized ? "Baseline (Flash)" : "Baseline (most expensive)"}
          </span>
          <span className="font-mono text-[12.5px] text-[#8e8e96]">{usd(baseline)}</span>
        </div>
        <div className="mt-[9px] h-[6px] rounded-[3px] bg-[#26262b]">
          <div
            className="h-full rounded-[3px] bg-[#3a3a42] transition-all"
            style={{ width: `${Math.min(100, baselinePct)}%` }}
          />
        </div>
      </div>

      <div className="mt-[22px] text-[13px] text-[#8e8e96]">
        {saved > 0 ? (
          <>
            {unrealized ? "Could save" : "Saved"}{" "}
            <span className="font-mono text-[12.5px] text-[#4ade80]">{usd(saved)}</span>
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
            <span className="font-mono text-[12.5px] text-[#4ade80]">{usd(0)}</span> (0.0%) this period.
          </>
        )}
      </div>
    </div>
  );
}
