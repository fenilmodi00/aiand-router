"use client";

import Link from "next/link";

export function PioneerFooter() {
  return (
    <footer className="border-t border-[#1f1f25] bg-[#0c0608] pt-16 pb-12 text-[#8e8e96] text-xs">
      <div className="mx-auto max-w-[1240px] px-6 sm:px-10">
        
        {/* Main Footer Grid */}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-10 pb-16 border-b border-[#1f1f25]">
          
          {/* Brand & Mission (Spans 2 columns) */}
          <div className="col-span-2 space-y-4">
            <div className="flex items-center gap-2.5">
              <div className="size-7 rounded-lg bg-[#f2613c] flex items-center justify-center font-bold text-white text-xs font-mono">
                AI&amp;
              </div>
              <span className="font-semibold text-sm tracking-tight text-white">
                AI&amp; ROUTER
              </span>
            </div>
            <p className="max-w-sm text-xs leading-relaxed text-[#8e8e96] font-light">
              An inference API built for developers who&apos;d rather ship than babysit a GPU cluster.
            </p>
            <div className="font-mono text-[11px] text-[#71717a] pt-2">
              Model Router Alias: <code className="text-[#f2613c]">ai&amp;/auto</code> · Endpoint: <code className="text-white">http://127.0.0.1:8000/v1</code>
            </div>
          </div>

          {/* Column 1: Developers */}
          <div className="space-y-3">
            <div className="font-mono text-xs uppercase text-white font-semibold tracking-wider">
              Developers
            </div>
            <ul className="space-y-2 font-light">
              <li><Link href="/" className="hover:text-white transition">Model Router</Link></li>
              <li><Link href="/playground" className="hover:text-white transition">Playground</Link></li>
              <li><Link href="/routers/auto" className="hover:text-white transition">Operator Console</Link></li>
              <li><Link href="/models" className="hover:text-white transition">Model Catalog</Link></li>
              <li><a href="https://docs.aiand.com" target="_blank" rel="noreferrer" className="hover:text-white transition">Documentation</a></li>
            </ul>
          </div>

          {/* Column 2: Integrations */}
          <div className="space-y-3">
            <div className="font-mono text-xs uppercase text-white font-semibold tracking-wider">
              Integrations
            </div>
            <ul className="space-y-2 font-light">
              <li><a href="#integrations" className="hover:text-white transition">OpenCode</a></li>
              <li><a href="#integrations" className="hover:text-white transition">Claude Code</a></li>
              <li><a href="#integrations" className="hover:text-white transition">Cursor IDE</a></li>
              <li><a href="#integrations" className="hover:text-white transition">Python SDK</a></li>
              <li><a href="#integrations" className="hover:text-white transition">Anthropic Adapter</a></li>
            </ul>
          </div>

          {/* Column 3: Connect */}
          <div className="space-y-3">
            <div className="font-mono text-xs uppercase text-white font-semibold tracking-wider">
              Connect
            </div>
            <ul className="space-y-2 font-light">
              <li><a href="https://github.com" target="_blank" rel="noreferrer" className="hover:text-white transition">GitHub ↗</a></li>
              <li><a href="https://x.com" target="_blank" rel="noreferrer" className="hover:text-white transition">X / Twitter ↗</a></li>
              <li><a href="https://discord.com" target="_blank" rel="noreferrer" className="hover:text-white transition">Discord Community ↗</a></li>
              <li><a href="mailto:support@aiand.com" className="hover:text-white transition">Support</a></li>
            </ul>
          </div>

        </div>

        {/* Bottom Bar */}
        <div className="mt-8 flex flex-col sm:flex-row items-center justify-between gap-4 font-mono text-[11px] text-[#71717a]">
          <div>
            © 2026 AI&amp; Technologies. All rights reserved.
          </div>
          <div className="flex items-center gap-6">
            <span className="text-[#4ade80]">● In-process Scorer &lt;8.4ms (ai&amp;/auto)</span>
            <span>SWE-bench Verified Promotion Gated</span>
          </div>
        </div>

      </div>
    </footer>
  );
}
