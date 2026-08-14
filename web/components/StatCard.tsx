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
    <Card className="gap-0 py-5">
      <CardContent className="px-[22px]">
        <div className="mb-4 text-[11px] font-medium tracking-[0.08em] text-muted-foreground uppercase">
          {label}
        </div>
        <div className={cn("text-[26px] font-medium tracking-tight", green && "text-success")}>
          {value}
        </div>
        {sub ? <div className="mt-2 font-mono text-xs text-muted-foreground">{sub}</div> : null}
      </CardContent>
    </Card>
  );
}
