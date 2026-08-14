"use client";

import { useState } from "react";
import { 
  CheckIcon, 
  CopyIcon, 
  TerminalIcon, 
  Code2Icon, 
  CpuIcon, 
  SparklesIcon,
  LaptopIcon
} from "lucide-react";
import { Badge } from "@/components/ui/badge";

type IntegrationTab = "opencode" | "claude-code" | "cursor" | "python" | "curl";

const INTEGRATION_SNIPPETS: Record<IntegrationTab, { title: string; filename?: string; code: string; desc: string }> = {
  opencode: {
    title: "OpenCode",
    filename: "~/.config/opencode/config.json",
    desc: "Seamless drop-in provider for OpenCode autonomous coding agent.",
    code: `{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "aiand-router": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "AI& Router",
      "options": {
        "baseURL": "http://127.0.0.1:8000/v1",
        "apiKey": "change-me"
      },
      "models": {
        "ai&/auto": { "name": "ai&/auto" }
      }
    }
  }
}`,
  },
  "claude-code": {
    title: "Claude Code",
    filename: "Terminal / Environment",
    desc: "Route Claude Code agentic turns through AI& Router proxy.",
    code: `# Set proxy endpoint & model alias in your shell
export ANTHROPIC_BASE_URL="http://127.0.0.1:8000"
export ANTHROPIC_API_KEY="change-me"
export ANTHROPIC_MODEL="ai&/auto"

# Run Claude Code normally
claude`,
  },
  cursor: {
    title: "Cursor",
    filename: "Cursor Settings → Models",
    desc: "Configure Cursor to route agent turns through AI& Router.",
    code: `1. Open Cursor Settings → Models
2. Enable "OpenAI Compatible Base URL"
3. Set Base URL: http://127.0.0.1:8000/v1
4. Set API Key: change-me
5. Add Model Name: ai&/auto
6. Select ai&/auto as your active model`,
  },
  python: {
    title: "Python SDK",
    filename: "agent.py",
    desc: "Call ai&/auto using the official OpenAI Python client.",
    code: `from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:8000/v1",
    api_key="change-me",
)

response = client.chat.completions.create(
    model="ai&/auto",
    messages=[
        {"role": "system", "content": "You are an expert coding assistant."},
        {"role": "user", "content": "Refactor parse_token in auth.py"}
    ],
    extra_headers={
        "x-agent-phase": "edit",
        "x-routing-effort": "medium"
    }
)

print(f"Selected: {response.response.headers.get('x-router-model')}")
print(response.choices[0].message.content)`,
  },
  curl: {
    title: "cURL / HTTP Wire",
    filename: "Terminal",
    desc: "Direct HTTP wire completion with phase and effort headers.",
    code: `curl http://127.0.0.1:8000/v1/chat/completions \\
  -H "Authorization: Bearer change-me" \\
  -H "Content-Type: application/json" \\
  -H "x-agent-phase: plan" \\
  -H "x-routing-effort: medium" \\
  -d '{
    "model": "ai&/auto",
    "messages": [
      {"role": "user", "content": "Design architecture for payment worker"}
    ]
  }'`,
  },
};

export function IntegrationsGrid() {
  const [activeTab, setActiveTab] = useState<IntegrationTab>("opencode");
  const [copied, setCopied] = useState<boolean>(false);

  const activeSnippet = INTEGRATION_SNIPPETS[activeTab];

  const copyToClipboard = () => {
    navigator.clipboard.writeText(activeSnippet.code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <section id="integrations" className="py-16 md:py-24 border-t border-[#1f1f25] bg-[#0c0608]">
      <div className="mx-auto max-w-[1240px] px-6 sm:px-10">
        
        {/* Section Header */}
        <div className="max-w-3xl mb-14">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-[#f2613c]/30 bg-[#f2613c]/10 text-[#f2613c] text-xs font-mono font-medium tracking-wide mb-4">
            60-SECOND INTEGRATION
          </div>
          <h2 className="text-3xl sm:text-4xl md:text-5xl font-normal tracking-tight text-white leading-tight">
            Works with Every Coding Harness &amp; Tool
          </h2>
          <p className="mt-4 text-base text-[#8e8e96] font-light leading-relaxed">
            No proprietary SDKs required. AI&amp; Router is 100% wire-compatible with standard
            OpenAI and Anthropic endpoints. Point your tool at <code className="text-[#f2613c] font-mono">http://127.0.0.1:8000/v1</code> with <code className="text-[#f2613c] font-mono">ai&amp;/auto</code>.
          </p>
        </div>

        {/* Integration Tabs & Code Box */}
        <div className="max-w-4xl rounded-3xl border border-[#232329] bg-[#101013] p-6 sm:p-9 shadow-2xl">
          
          {/* Tab Selector */}
          <div className="flex flex-wrap items-center justify-between gap-3 pb-6 border-b border-[#1f1f25]">
            <div className="flex flex-wrap items-center gap-1.5 p-1 rounded-xl bg-[#0c0608] border border-[#232329]">
              {(Object.keys(INTEGRATION_SNIPPETS) as IntegrationTab[]).map((tabKey) => {
                const active = tabKey === activeTab;
                return (
                  <button
                    key={tabKey}
                    onClick={() => setActiveTab(tabKey)}
                    type="button"
                    className={`px-3.5 py-1.5 rounded-lg text-xs font-mono transition cursor-pointer select-none ${
                      active
                        ? "bg-[#f2613c] text-white font-bold shadow-xs"
                        : "text-[#8e8e96] hover:text-white hover:bg-[#1a1a20]"
                    }`}
                  >
                    {INTEGRATION_SNIPPETS[tabKey].title}
                  </button>
                );
              })}
            </div>

            {/* Copy Button */}
            <button
              onClick={copyToClipboard}
              type="button"
              className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl border border-[#2d2d34] bg-[#0c0608] text-xs font-medium text-white hover:bg-[#1a1a20] transition cursor-pointer select-none"
            >
              {copied ? (
                <>
                  <CheckIcon className="size-3.5 text-[#4ade80]" />
                  <span className="text-[#4ade80] font-semibold font-mono">Copied!</span>
                </>
              ) : (
                <>
                  <CopyIcon className="size-3.5 text-[#8e8e96]" />
                  <span className="font-mono text-[#8e8e96]">Copy Config</span>
                </>
              )}
            </button>
          </div>

          {/* Description & File Path */}
          <div className="mt-4 flex flex-wrap items-center justify-between gap-2 text-xs">
            <span className="text-neutral-300 font-light">
              {activeSnippet.desc}
            </span>
            {activeSnippet.filename && (
              <span className="font-mono text-[11px] text-[#8e8e96] bg-[#0c0608] px-2.5 py-1 rounded-lg border border-[#1f1f25]">
                {activeSnippet.filename}
              </span>
            )}
          </div>

          {/* Code Block */}
          <div className="mt-4 p-4 sm:p-5 rounded-2xl bg-[#0c0608] border border-[#1f1f25] font-mono text-xs text-neutral-200 overflow-x-auto leading-relaxed">
            <pre>{activeSnippet.code}</pre>
          </div>

        </div>

      </div>
    </section>
  );
}
