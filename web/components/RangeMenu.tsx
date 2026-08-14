"use client";

import Link from "next/link";
import { CalendarIcon, ChevronDownIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { RANGE_LABEL } from "@/lib/format";
import type { Range } from "@/lib/types";

export function RangeMenu({ range, hrefs }: { range: Range; hrefs: Record<Range, string> }) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger render={<Button variant="outline" size="sm" className="h-8" />}>
        <CalendarIcon data-icon="inline-start" />
        {RANGE_LABEL[range]}
        <ChevronDownIcon data-icon="inline-end" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuGroup>
          {(Object.keys(RANGE_LABEL) as Range[]).map((r) => (
            <DropdownMenuItem key={r} render={<Link href={hrefs[r]} />}>
              {RANGE_LABEL[r]}
            </DropdownMenuItem>
          ))}
        </DropdownMenuGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

export function LinkToggle({
  value,
  items,
}: {
  value: string;
  items: { value: string; label: string; href: string }[];
}) {
  return (
    <ToggleGroup value={[value]} spacing={0} className="rounded-lg bg-muted p-0.5">
      {items.map((item) => (
        <ToggleGroupItem
          key={item.value}
          value={item.value}
          size="sm"
          render={<Link href={item.href} />}
          nativeButton={false}
        >
          {item.label}
        </ToggleGroupItem>
      ))}
    </ToggleGroup>
  );
}
