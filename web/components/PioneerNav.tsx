"use client";

import Link from "next/link";
import { ChevronRightIcon, SparklesIcon } from "lucide-react";
import { Button } from "@/components/ui/button";

export function PioneerNav() {
  return (
    <header className="sticky top-0 z-50 w-full border-b border-[#232329]/70 bg-[#0c0608]/90 backdrop-blur-xl">
      <div className="mx-auto max-w-[1240px] px-6 sm:px-10 h-16 flex items-center justify-between">
        
        {/* Brand Logo & Tag */}
        <div className="flex items-center gap-6">
          <Link href="/" className="flex items-center gap-2.5 group">
            <div className="size-7 rounded-lg bg-[#f2613c] flex items-center justify-center font-bold text-white text-xs shadow-sm transition group-hover:bg-[#ff7345]">
              <span className="font-mono text-sm tracking-tighter">AI&amp;</span>
            </div>
            <span className="font-semibold text-[15px] tracking-tight text-white flex items-center gap-1.5">
              AI&amp; <span className="text-[#8e8e96] font-normal text-xs font-mono">/ router</span>
            </span>
          </Link>

          {/* Status pill */}
          <div className="hidden lg:flex items-center gap-1.5 px-2.5 py-0.5 rounded-full border border-[#2b2225] bg-[#140e10] text-[11px] font-mono text-[#f2613c]">
            <span className="size-1.5 rounded-full bg-[#f2613c] animate-pulse" />
            <span>ai&amp;/auto active</span>
          </div>
        </div>

        {/* Nav Links */}
        <nav className="hidden md:flex items-center gap-7 text-[13px] text-[#8e8e96] font-medium">
          <Link href="/" className="text-white hover:text-white transition">Model Router</Link>
          <a href="#benchmarks" className="hover:text-white transition">Benchmarks</a>
          <a href="#how-it-works" className="hover:text-white transition">How it works</a>
          <a href="#simulator" className="hover:text-white transition">Simulator</a>
          <a href="#calculator" className="hover:text-white transition">Pricing &amp; ROI</a>
          <a href="https://docs.aiand.com" target="_blank" rel="noreferrer" className="hover:text-white transition">Docs</a>
        </nav>

        {/* Actions */}
        <div className="flex items-center gap-3">
          <Button
            render={<Link href="/routers/auto" />}
            nativeButton={false}
            variant="outline"
            className="h-8 rounded-full border-[#2d2d34] bg-[#101013] px-3.5 text-xs text-neutral-300 hover:bg-[#1a1a1f] hover:text-white transition cursor-pointer"
          >
            Console
          </Button>
          <Button
            render={<Link href="/playground" />}
            nativeButton={false}
            className="h-8 rounded-full bg-white px-4 text-xs font-semibold text-black hover:bg-neutral-200 transition shadow-xs cursor-pointer"
          >
            Get started
          </Button>
        </div>

      </div>
    </header>
  );
}
