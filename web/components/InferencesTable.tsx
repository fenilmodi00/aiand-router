"use client";

import { useState } from "react";
import { LayoutGridIcon, ListIcon, SearchIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Empty, EmptyDescription, EmptyHeader, EmptyTitle } from "@/components/ui/empty";
import {
  InputGroup,
  InputGroupAddon,
  InputGroupInput,
} from "@/components/ui/input-group";
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { shortTs } from "@/lib/format";
import type { Candidate, Inference } from "@/lib/types";

const PAGE_SIZE = 25;

function qualityCell(row: Inference): string {
  if (row.tests_passed === true) return "pass";
  if (row.tests_passed === false) return "fail";
  if (row.llmaj_score != null) return String(row.llmaj_score);
  return "—";
}

export function InferencesTable({
  rows,
  range,
  q,
  model,
  candidates,
  error,
}: {
  rows: Inference[];
  range: string;
  q: string;
  model: string;
  candidates: Candidate[];
  error?: string | null;
}) {
  const [grid, setGrid] = useState(false);
  const [page, setPage] = useState(1);
  const [modelValue, setModelValue] = useState<string | null>(model || null);
  const items = [
    { label: "Model", value: null },
    ...candidates.map((c) => ({ label: c.display_name, value: c.id })),
  ];
  const emptyMsg = error ? `Gateway error: ${error}` : "No data matches your filters.";
  const total = rows.length;
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const safePage = Math.min(page, pageCount);
  const start = (safePage - 1) * PAGE_SIZE;
  const pageRows = rows.slice(start, start + PAGE_SIZE);



  const totalTokens = rows.reduce((s, r) => s + (r.tokens_in || 0) + (r.tokens_out || 0), 0);
  const totalSpend = rows.reduce((s, r) => s + (r.cost_usd || 0), 0);
  const totalSavings = rows.reduce((s, r) => s + (r.savings_usd || 0), 0);
  const savingsPct = totalSpend + totalSavings > 0 ? (totalSavings / (totalSpend + totalSavings)) * 100 : 0;

  return (
    <div className="flex flex-col gap-4">
      {/* Overview Summary Banner */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 rounded-xl border border-[#222] bg-[#0c0c0e] p-3.5 text-[12.5px]">
        <div className="flex flex-col">
          <span className="text-[11px] text-muted-foreground uppercase font-medium">Routed Requests</span>
          <span className="text-base font-semibold text-white font-mono">{total.toLocaleString("en-US")}</span>
        </div>
        <div className="flex flex-col">
          <span className="text-[11px] text-muted-foreground uppercase font-medium">Token Volume</span>
          <span className="text-base font-semibold text-white font-mono">{totalTokens.toLocaleString("en-US")}</span>
        </div>
        <div className="flex flex-col">
          <span className="text-[11px] text-muted-foreground uppercase font-medium">Total Cost</span>
          <span className="text-base font-semibold text-white font-mono">${totalSpend.toFixed(4)}</span>
        </div>
        <div className="flex flex-col">
          <span className="text-[11px] text-emerald-400 uppercase font-medium">Total Saved</span>
          <span className="text-base font-semibold text-[#4ade80] font-mono">
            +${totalSavings.toFixed(4)} {savingsPct > 0 ? `(${Math.round(savingsPct)}%)` : ""}
          </span>
        </div>
      </div>

      <form className="flex flex-wrap gap-3" action="/routers/auto" method="get">
        <input type="hidden" name="range" value={range} />
        <input type="hidden" name="model" value={modelValue ?? ""} />
        <InputGroup className="h-10 min-w-[180px] flex-1">
          <InputGroupAddon>
            <SearchIcon />
          </InputGroupAddon>
          <InputGroupInput
            type="search"
            name="q"
            defaultValue={q}
            placeholder="Search inferences..."
            aria-label="Search inferences"
          />
        </InputGroup>
        <Select items={items} value={modelValue} onValueChange={(v) => setModelValue(v as string | null)}>
          <SelectTrigger className="h-10" aria-label="Model">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectGroup>
              {items.map((item) => (
                <SelectItem key={String(item.value)} value={item.value}>
                  {item.label}
                </SelectItem>
              ))}
            </SelectGroup>
          </SelectContent>
        </Select>
        <Button type="submit" variant="outline" className="h-10">
          Filter
        </Button>
        <ToggleGroup
          value={[grid ? "grid" : "list"]}
          onValueChange={(v) => {
            if (v[0]) setGrid(v[0] === "grid");
          }}
          spacing={0}
          className="rounded-lg border border-input"
        >
          <ToggleGroupItem value="grid" aria-label="Grid view" className="size-10">
            <LayoutGridIcon />
          </ToggleGroupItem>
          <ToggleGroupItem value="list" aria-label="List view" className="size-10">
            <ListIcon />
          </ToggleGroupItem>
        </ToggleGroup>
      </form>
      {grid ? (
        rows.length === 0 ? (
          <Empty className="min-h-[120px] border">
            <EmptyHeader>
              <EmptyTitle>No inferences</EmptyTitle>
              <EmptyDescription>{emptyMsg}</EmptyDescription>
            </EmptyHeader>
          </Empty>
        ) : (
          <div className="grid grid-cols-[repeat(auto-fill,minmax(260px,1fr))] gap-3">
            {pageRows.map((row, i) => (
              <Card key={`${row.ts}-${i}`} size="sm">
                <CardHeader>
                  <CardTitle className="text-[11px] tracking-[0.06em] text-muted-foreground uppercase">
                    Time
                  </CardTitle>
                </CardHeader>
                <CardContent className="flex flex-col gap-2.5">
                  <div>{shortTs(row.ts)}</div>
                  <div className="text-[11px] tracking-[0.06em] text-muted-foreground uppercase">Model</div>
                  <div>
                    {row.selected || "—"}
                    <div className="font-mono text-[11px] text-muted-foreground">{row.path}</div>
                  </div>
                  <div className="flex justify-between text-[11.5px]">
                    <span className="text-muted-foreground">Cost: ${row.cost_usd.toFixed(4)}</span>
                    {row.savings_usd != null && row.savings_usd > 0 && (
                      <span className="text-[#4ade80] font-mono">Saved: +${row.savings_usd.toFixed(4)}</span>
                    )}
                  </div>
                  <div className="text-[11px] tracking-[0.06em] text-muted-foreground uppercase">
                    Status / cache
                  </div>
                  <div>
                    {row.status} · {row.cache_hit ? "hit" : "miss"}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )
      ) : (
        <div className="overflow-hidden rounded-lg border bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Time</TableHead>
                <TableHead>Model</TableHead>
                <TableHead>Input</TableHead>
                <TableHead className="text-right">Tokens</TableHead>
                <TableHead className="text-right">E2E latency</TableHead>
                <TableHead className="text-right">TTFT</TableHead>
                <TableHead className="text-right">Cost</TableHead>
                <TableHead className="text-right text-[#4ade80]">Savings</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Cache</TableHead>
                <TableHead className="text-right">LLMaJ</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.length === 0 ? (
                <TableRow>
                    <TableCell colSpan={11} className="py-12 text-center text-muted-foreground">
                    {emptyMsg}
                  </TableCell>
                </TableRow>
              ) : (
                pageRows.map((row, i) => (
                  <TableRow key={`${row.ts}-${row.selected}-${i}`}>
                    <TableCell>{shortTs(row.ts)}</TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1.5 flex-wrap">
                        <span className="font-medium text-white">{row.selected || "—"}</span>
                        {row.escalated_from && (
                          <span className="rounded bg-amber-500/15 border border-amber-500/30 px-1.5 py-0.2 text-[9.5px] font-semibold text-amber-300">
                            Escalated from {row.escalated_from}
                          </span>
                        )}
                      </div>
                      <div className="font-mono text-[11px] text-muted-foreground flex items-center gap-1.5 mt-0.5">
                        <span>{row.path}</span>
                        {row.phase ? <span>· {row.phase}</span> : null}
                        {row.rule ? <span className="text-neutral-400">({row.rule})</span> : null}
                      </div>
                    </TableCell>
                    <TableCell>{row.tokens_in}</TableCell>
                    <TableCell className="text-right">{row.tokens_out}</TableCell>
                    <TableCell className="text-right">{row.latency_ms} ms</TableCell>
                    <TableCell className="text-right">{row.ttft_ms == null ? "—" : `${row.ttft_ms} ms`}</TableCell>
                    <TableCell className="text-right font-mono text-neutral-300">${row.cost_usd.toFixed(4)}</TableCell>
                    <TableCell className="text-right font-mono text-[#4ade80] font-medium">
                      {row.savings_usd != null && row.savings_usd > 0 ? `+$${row.savings_usd.toFixed(4)}` : "—"}
                    </TableCell>
                    <TableCell>{row.status}</TableCell>
                    <TableCell className="text-right">{row.cache_hit ? "hit" : "—"}</TableCell>
                    <TableCell className="text-right">{qualityCell(row)}</TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>
      )}
      {total > 0 ? (
        <div className="flex items-center justify-end gap-3">
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={safePage <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            Previous
          </Button>
          <span className="text-sm tabular-nums text-muted-foreground">
            {start + 1}–{start + pageRows.length} of {total}
            <span className="ml-2 text-muted-foreground/70">
              {safePage} / {pageCount}
            </span>
          </span>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={safePage >= pageCount}
            onClick={() => setPage((p) => Math.min(pageCount, p + 1))}
          >
            Next
          </Button>
        </div>
      ) : null}
    </div>
  );
}
