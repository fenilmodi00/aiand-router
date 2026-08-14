import { ChevronsLeftIcon } from "lucide-react";
import { Button } from "@/components/ui/button";

export function HowToRail() {
  return (
    <aside className="fixed inset-y-0 right-0 z-40 flex w-11 flex-col items-center border-l border-sidebar-border bg-background pt-3.5">
      <Button variant="outline" size="icon-xs" className="size-7 rounded-[7px]" aria-hidden tabIndex={-1}>
        <ChevronsLeftIcon />
      </Button>
      <span className="mt-7 text-[11px] font-medium tracking-[0.16em] text-muted-foreground uppercase [text-orientation:mixed] [writing-mode:vertical-rl]">
        How to inference
      </span>
    </aside>
  );
}
