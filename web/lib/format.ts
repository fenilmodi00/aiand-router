import type { Range } from "./types";

export function usd(n: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(Number.isFinite(n) ? n : 0);
}

export function pct(n: number): string {
  return `${(Number.isFinite(n) ? n : 0).toFixed(1)}%`;
}

export function parseRange(raw: string | undefined): Range {
  if (raw === "24h" || raw === "7d" || raw === "30d" || raw === "all") return raw;
  return "30d";
}

export const RANGE_LABEL: Record<Range, string> = {
  "24h": "Last 24 hours",
  "7d": "Last 7 days",
  "30d": "Last 30 days",
  all: "All time",
};

export function shortTs(ts: string | null): string {
  if (!ts) return "—";
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return ts.slice(0, 16);
  const iso = d.toISOString();
  return `${iso.slice(5, 10)} ${iso.slice(11, 16)}`;
}

export function colorFor(id: string, i: number, palette: string[]): string {
  let h = 0;
  for (let k = 0; k < id.length; k++) h = (h * 31 + id.charCodeAt(k)) | 0;
  if (i >= 0 && i < palette.length) return palette[i]!;
  return palette[Math.abs(h) % palette.length]!;
}
