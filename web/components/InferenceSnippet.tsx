"use client";

import { useState } from "react";
import { toast } from "sonner";
import { CopyIcon } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { cn } from "@/lib/utils";

const SNIPPETS: Record<string, { label: string; code: string; lang: string }> = {
  curl: {
    label: "cURL (OpenAI)",
    lang: "bash",
    code: `curl -X POST "http://127.0.0.1:8000/v1/chat/completions" \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer <YOUR_ROUTER_KEY>" \\
  -d '{
    "model": "aiand/auto",
    "messages": [
      { "role": "system", "content": "You are a helpful assistant." },
      { "role": "user", "content": "Extract key entities from this document." }
    ],
    "stream": false
  }'`,
  },
  claude: {
    label: "Claude Code",
    lang: "bash",
    code: `# Configure Claude Code to use AIand Coding Router
export ANTHROPIC_BASE_URL="http://127.0.0.1:8000"
export ANTHROPIC_API_KEY="<YOUR_ROUTER_KEY>"
export ANTHROPIC_CUSTOM_MODEL_OPTION="aiand/auto"

# Run Claude Code with automated model routing
claude --model aiand/auto`,
  },
  opencode: {
    label: "OpenCode",
    lang: "json",
    code: `// opencode.json or ~/.config/opencode/config.json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "aiand-router": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "AIand Router",
      "options": {
        "baseURL": "http://127.0.0.1:8000/v1",
        "apiKey": "<YOUR_ROUTER_KEY>"
      },
      "models": {
        "aiand/auto": { "name": "aiand/auto" }
      }
    }
  }
}`,
  },
  codex: {
    label: "Codex CLI",
    lang: "toml",
    code: `# ~/.codex/config.toml
[providers.aiand_router]
base_url = "http://127.0.0.1:8000/v1"
api_key = "<YOUR_ROUTER_KEY>"
wire_api = "responses"

[models."aiand/auto"]
provider = "aiand_router"
model = "aiand/auto"`,
  },
};

export function InferenceSnippet() {
  const [tab, setTab] = useState("curl");
  const active = SNIPPETS[tab] || SNIPPETS.curl;

  return (
    <Card id="run-inference" className="gap-0 py-0 overflow-hidden border border-[#222] bg-[#0c0c0e]">
      <CardHeader className="flex flex-row items-center gap-2.5 border-b border-[#1f1f23] py-3.5 px-6">
        <div className="flex items-center gap-2">
          {Object.entries(SNIPPETS).map(([key, item]) => (
            <button
              key={key}
              type="button"
              onClick={() => setTab(key)}
              className={cn(
                "rounded-lg px-3 py-1.5 text-xs font-medium transition",
                tab === key
                  ? "bg-[#1f1f23] text-white shadow-xs"
                  : "text-neutral-400 hover:text-neutral-200 hover:bg-[#151518]",
              )}
            >
              {item.label}
            </button>
          ))}
        </div>
        <span className="ml-auto flex items-center gap-2.5">
          <Badge variant="outline" className="h-7 rounded-md px-2.5 text-[11px] font-mono border-[#333]">
            aiand/auto
          </Badge>
          <Button
            variant="outline"
            size="sm"
            type="button"
            className="h-7 text-xs"
            onClick={() => {
              navigator.clipboard.writeText(active.code).then(() => toast.success("Copied to clipboard"));
            }}
          >
            <CopyIcon className="size-3.5 mr-1" />
            Copy
          </Button>
        </span>
      </CardHeader>
      <CardContent className="p-0">
        <pre className="overflow-x-auto p-5 font-mono text-[12.5px] leading-[1.65] text-neutral-300 bg-[#070709]">
          {active.code}
        </pre>
      </CardContent>
    </Card>
  );
}
