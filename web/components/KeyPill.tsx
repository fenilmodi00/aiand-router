"use client";

import { useState } from "react";
import { toast } from "sonner";
import { CopyIcon, EyeIcon, EyeOffIcon } from "lucide-react";
import {
  InputGroup,
  InputGroupAddon,
  InputGroupButton,
  InputGroupInput,
} from "@/components/ui/input-group";
import type { MaskedKey } from "@/lib/types";

export function KeyPill({ masked }: { masked: MaskedKey }) {
  const [shown, setShown] = useState(true);

  async function copy() {
    try {
      const r = await fetch("/api/keys", { method: "POST" });
      const data = (await r.json()) as { key?: string; error?: string };
      const text = data.key || masked.masked;
      await navigator.clipboard.writeText(text);
      toast.success("Copied");
    } catch {
      await navigator.clipboard.writeText(masked.masked);
      toast.success("Copied");
    }
  }

  return (
    <InputGroup className="h-auto bg-muted py-1 font-mono text-[12.5px]">
      <InputGroupInput
        readOnly
        value={shown ? masked.masked : masked.hidden}
        aria-label="API key"
        className="text-muted-foreground"
      />
      <InputGroupAddon align="inline-end">
        <InputGroupButton
          size="icon-xs"
          aria-label="Toggle key visibility"
          onClick={() => setShown((s) => !s)}
        >
          {shown ? <EyeIcon /> : <EyeOffIcon />}
        </InputGroupButton>
        <InputGroupButton size="icon-xs" aria-label="Copy API key" onClick={copy}>
          <CopyIcon />
        </InputGroupButton>
      </InputGroupAddon>
    </InputGroup>
  );
}
