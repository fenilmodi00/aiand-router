import { PioneerNav } from "@/components/PioneerNav";
import { PioneerHero } from "@/components/PioneerHero";
import { PioneerBenchmarkCard } from "@/components/PioneerBenchmarkCard";
import { PioneerFeaturePillars } from "@/components/PioneerFeaturePillars";
import { InteractiveRouterSimulator } from "@/components/InteractiveRouterSimulator";
import { TrainedVsRulesSection } from "@/components/TrainedVsRulesSection";
import { RoiCalculator } from "@/components/RoiCalculator";
import { TelemetryShowcase } from "@/components/TelemetryShowcase";
import { IntegrationsGrid } from "@/components/IntegrationsGrid";
import { PioneerFooter } from "@/components/PioneerFooter";

export default function PioneerLandingPage() {
  return (
    <div className="min-h-screen bg-[#0c0608] text-white selection:bg-[#f2613c] selection:text-white font-sans antialiased">
      
      {/* 1. Pioneer Navigation Bar */}
      <PioneerNav />

      <main>
        {/* 2. Pioneer Hero with Live Routing Flow */}
        <PioneerHero />

        {/* 3. Pioneer Benchmarks (SWE-Bench Comparison) */}
        <PioneerBenchmarkCard />

        {/* 4. Pioneer 3-Pillar Feature Showcase (01, 02, 03) */}
        <PioneerFeaturePillars />

        {/* 5. Live Interactive Agent Step Simulator */}
        <div id="simulator">
          <InteractiveRouterSimulator />
        </div>

        {/* 6. ML-Trained vs Rule-Based Architecture Deep-Dive */}
        <div id="architecture">
          <TrainedVsRulesSection />
        </div>

        {/* 7. Token Economics & ROI Calculator */}
        <div id="calculator">
          <RoiCalculator />
        </div>

        {/* 8. Telemetry & Latency Profiles */}
        <TelemetryShowcase />

        {/* 9. 60-Second Integrations (OpenCode, Claude Code, Cursor, Python) */}
        <IntegrationsGrid />
      </main>

      {/* 10. Pioneer Footer */}
      <PioneerFooter />

    </div>
  );
}
