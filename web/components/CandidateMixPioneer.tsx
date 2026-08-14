import { ModelLogo } from "@/lib/provider-logos";
import { pct } from "@/lib/format";
import type { MixRow } from "@/components/RoutingPipeline";

const MODEL_COLORS: string[] = [
  "#f2613c", // orange / pioneer
  "#3b82f6", // blue / deepseek
  "#4ade80", // green
  "#c8a06a", // gold / kimi
  "#a855f7", // purple
  "#2dd4bf", // teal
  "#ec4899", // pink
];

/**
 * Pioneer-style candidate mix with inline meter bars.
 */
export function CandidateMixPioneer({
  rows,
  total,
  emptyLabel = "No routed requests yet.",
  useOrg = false,
  orgSampleN = 0,
}: {
  rows: MixRow[];
  total: number;
  emptyLabel?: string;
  useOrg?: boolean;
  orgSampleN?: number;
}) {
  const hasMix = total > 0 && rows.some((r) => r.count > 0);

  return (
    <div className="flex flex-col gap-0 rounded-2xl border border-[#1a1a1e] bg-[#08080a] p-6 shadow-xs">
      <div className="text-[15px] font-semibold text-white">Candidate mix</div>
      <div className="mt-1 text-[13px] text-[#71717a]">
        {useOrg
          ? `Models on the last ${orgSampleN} org requests — none of these went through the router.`
          : `Which models the router picked across the last ${total} routed requests.`}
      </div>

      {!hasMix ? (
        <div className="mt-5 flex min-h-[140px] items-center justify-center rounded-xl border border-dashed border-[#222226] text-[13px] text-[#71717a]">
          {emptyLabel}
        </div>
      ) : (
        <div className="mt-5 flex flex-col gap-4">
          {rows
            .filter((r) => r.count > 0)
            .map((r, idx) => {
              const barColor = MODEL_COLORS[idx % MODEL_COLORS.length];
              return (
                <div key={r.id} className="flex flex-col gap-2">
                  <div className="flex items-center justify-between text-[13px]">
                    <div className="flex items-center gap-2">
                      <ModelLogo modelId={r.id} className="size-3.5" />
                      <span className="font-medium text-white">{r.display_name}</span>
                    </div>
                    <span className="font-mono text-[12px] text-[#71717a]">
                      {r.count} · {pct(r.pct)}
                    </span>
                  </div>
                  <div className="h-[5px] w-full rounded-full bg-[#18181c] overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all"
                      style={{
                        width: `${Math.min(100, r.pct)}%`,
                        backgroundColor: barColor,
                      }}
                    />
                  </div>
                </div>
              );
            })}
        </div>
      )}
    </div>
  );
}
