import { pct } from "@/lib/format";
import type { MixRow } from "@/components/RoutingPipeline";

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
    <div className="card flex flex-col gap-0 rounded-[14px] border border-[#232329] bg-[#101013] p-[22px_24px]">
      <div className="text-[15px] font-semibold">Candidate mix</div>
      <div className="mt-1 text-[13px] text-[#8e8e96]">
        {useOrg
          ? `Models on the last ${orgSampleN} org requests — none of these went through the router.`
          : `Which models the router picked across the last ${total} routed requests.`}
      </div>

      {!hasMix ? (
        <div className="mt-[18px] flex min-h-[150px] items-center justify-center rounded-[10px] border border-dashed border-[#2c2c33] text-[13px] text-[#8e8e96]">
          {emptyLabel}
        </div>
      ) : (
        <div className="mt-5 flex flex-col gap-5">
          {rows
            .filter((r) => r.count > 0)
            .map((r) => (
              <div key={r.id} className="meter-row">
                <div className="row-head flex items-center justify-between text-[13px]">
                  <span>{r.display_name}</span>
                  <span className="font-mono text-[12.5px] text-[#8e8e96]">
                    {r.count} · {pct(r.pct)}
                  </span>
                </div>
                <div className="mt-[9px] h-[6px] rounded-[3px] bg-[#26262b]">
                  <div
                    className="h-full rounded-[3px] bg-[#4ade80] transition-all"
                    style={{ width: `${Math.min(100, r.pct)}%` }}
                  />
                </div>
              </div>
            ))}
        </div>
      )}
    </div>
  );
}
