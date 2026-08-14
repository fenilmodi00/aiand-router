import type { Range } from "./types";

export function usd(n: number): string {
  const v = Number.isFinite(n) ? n : 0;
  const abs = Math.abs(v);
  // LLM hop costs are often << $0.01; 2-dp currency would lie as $0.00.
  const digits = abs > 0 && abs < 0.01 ? 6 : abs < 1 ? 4 : 2;
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(v);
}

export function compact(n: number): string {
  return new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(
    Number.isFinite(n) ? n : 0,
  );
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
  const d = new Date(ts.includes("T") || ts.includes(" ") ? ts : ts.replace(" ", "T"));
  if (Number.isNaN(d.getTime())) {
    const m = ts.match(/(\d{2}-\d{2})[T ](\d{2}:\d{2})/);
    return m ? `${m[1]} ${m[2]}` : ts.slice(0, 11);
  }
  const iso = d.toISOString();
  const hm = iso.slice(11, 16);
  return hm === "00:00" ? iso.slice(5, 10) : `${iso.slice(5, 10)} ${hm}`;
}

export function colorFor(id: string, i: number, palette: string[]): string {
  let h = 0;
  for (let k = 0; k < id.length; k++) h = (h * 31 + id.charCodeAt(k)) | 0;
  if (i >= 0 && i < palette.length) return palette[i]!;
  return palette[Math.abs(h) % palette.length]!;
}
