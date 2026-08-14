import Link from "next/link";
import { ChevronRightIcon, PlusIcon } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { getOverview } from "@/lib/api";

export default async function RoutersPage() {
  const overview = await getOverview("all");
  const n = overview.data?.candidates.filter((c) => c.enabled).length ?? overview.data?.candidates.length ?? 16;
  const meta = `Router · Auto · ${n || 16} candidates`;

  return (
    <div className="mx-auto max-w-[1360px] px-6 md:px-11 pt-[26px] pb-[120px] text-[#eaeaea]">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h2 className="text-[26px] font-semibold tracking-tight text-white">Routers</h2>
          <p className="mt-1 text-[13px] text-[#8e8e96]">
            Inference routers configured in this workspace.
          </p>
        </div>
        <button
          type="button"
          className="inline-flex items-center gap-1.5 rounded-lg border border-[#2d2d2d] bg-[#101013] px-3.5 py-2 text-xs font-medium text-white shadow-xs transition hover:bg-[#1a1a1e]"
        >
          <PlusIcon className="size-3.5" />
          New router
        </button>
      </div>

      {overview.error && !overview.ok ? (
        <Alert className="mb-4 border-destructive/50 bg-destructive/10">
          <AlertTitle>Gateway unreachable</AlertTitle>
          <AlertDescription>
            {overview.error}. Showing the local router row anyway.
          </AlertDescription>
        </Alert>
      ) : null}

      <div className="rounded-xl border border-[#232329] bg-[#101013] overflow-hidden">
        <Link
          href="/routers/auto"
          className="group relative block p-6 transition hover:bg-[#17171a]"
        >
          <div className="flex items-start justify-between">
            <div>
              <div className="text-[16px] font-semibold text-white group-hover:text-white">
                pioneer/auto
              </div>
              <div className="mt-1 font-mono text-[11px] tracking-[0.06em] text-[#8e8e96] uppercase">
                {meta}
              </div>
              <p className="mt-2.5 max-w-2xl text-[13px] text-[#8e8e96] leading-relaxed">
                Routes each request to the cheapest candidate that still meets the quality bar.
              </p>
            </div>
            <span className="inline-flex size-8 items-center justify-center rounded-lg text-[#8e8e96] group-hover:text-white group-hover:bg-[#232329] transition">
              <ChevronRightIcon className="size-4" />
            </span>
          </div>
        </Link>
      </div>
    </div>
  );
}
