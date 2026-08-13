"use client";

import { useState } from "react";
import type { MaskedKey } from "@/lib/types";

export function KeyPill({ masked }: { masked: MaskedKey }) {
  const [shown, setShown] = useState(true);
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      const r = await fetch("/api/keys", { method: "POST" });
      const data = (await r.json()) as { key?: string; error?: string };
      const text = data.key || masked.masked;
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1400);
    } catch {
      await navigator.clipboard.writeText(masked.masked);
    }
  }

  return (
    <div className="key-pill">
      <span className="grow">{shown ? masked.masked : masked.hidden}</span>
      <button className="icon-btn" type="button" aria-label="Toggle key visibility" onClick={() => setShown((s) => !s)}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
          <path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6-10-6-10-6z" />
          <circle cx="12" cy="12" r="2.5" />
        </svg>
      </button>
      <button className="icon-btn" type="button" aria-label={copied ? "Copied" : "Copy API key"} onClick={copy}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
          <rect x="9" y="9" width="12" height="12" rx="2" />
          <path d="M5 15V5a2 2 0 012-2h10" />
        </svg>
      </button>
    </div>
  );
}
