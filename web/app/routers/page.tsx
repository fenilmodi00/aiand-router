import Link from "next/link";
import { ChevronRightIcon } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { getOverview } from "@/lib/api";

export default async function RoutersPage() {
  const overview = await getOverview("all");
  const n = overview.data?.candidates.filter((c) => c.enabled).length ?? overview.data?.candidates.length ?? 0;
  const meta = n ? `Router · Auto · ${n} candidates` : "Router · Auto";

  return (
    <div className="mx-auto max-w-[1360px] px-11 pt-[26px] pb-[120px]">
      <div className="mb-[18px] flex items-end justify-between">
        <div>
          <h2 className="text-xl font-semibold">Routers</h2>
          <p className="mt-1 text-[13px] text-muted-foreground">
            Inference routers configured in this workspace.
          </p>
        </div>
      </div>
      {overview.error && !overview.ok ? (
        <Alert className="mb-4">
          <AlertTitle>Gateway unreachable</AlertTitle>
          <AlertDescription>
            {overview.error}. Showing the local router row anyway.
          </AlertDescription>
        </Alert>
      ) : null}
      <Card className="gap-0 py-0">
        <Link href="/routers/auto" className="relative block px-6 py-[22px] hover:bg-muted/40">
          <CardHeader className="p-0">
            <CardTitle className="text-[15px]">router/auto</CardTitle>
            <CardDescription className="font-mono text-[11px] tracking-[0.06em] uppercase">
              {meta}
            </CardDescription>
          </CardHeader>
          <CardContent className="mt-2.5 p-0 pr-7 text-[13px] text-muted-foreground">
            Routes each request to the cheapest candidate that still meets the quality bar.
          </CardContent>
          <ChevronRightIcon className="absolute top-1/2 right-6 -translate-y-1/2 text-muted-foreground" />
        </Link>
      </Card>
    </div>
  );
}
