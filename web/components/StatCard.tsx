import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export function StatCard({
  label,
  value,
  sub,
  green,
}: {
  label: string;
  value: string;
  sub?: string;
  green?: boolean;
}) {
  return (
    <Card className="gap-0 py-5 px-6 border border-[#232328] bg-[#0c0c0f] rounded-2xl shadow-xs">
      <CardContent className="p-0">
        <div className="text-[11px] font-semibold tracking-[0.08em] text-[#8e8e96] uppercase">
          {label}
        </div>
        <div className={cn("mt-3 text-[28px] font-semibold tracking-tight text-white font-mono leading-none", green && "text-[#4ade80]")}>
          {value}
        </div>
        {sub ? <div className="mt-2.5 font-mono text-[12px] text-[#71717a]">{sub}</div> : null}
      </CardContent>
    </Card>
  );
}
