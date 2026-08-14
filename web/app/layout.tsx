import { Inter, JetBrains_Mono } from "next/font/google";
import type { Metadata } from "next";
import { catalogCount, getModels } from "@/lib/api";
import { HowToRail } from "@/components/HowToRail";
import { Providers } from "@/components/providers";
import { Rail } from "@/components/Rail";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";
import { cn } from "@/lib/utils";
import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-sans" });
const mono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-mono" });

export const metadata: Metadata = {
  title: "Routers · AIand",
  description: "Local operator console for router/auto",
};

export const dynamic = "force-dynamic";

export default async function RootLayout({ children }: LayoutProps<"/">) {
  const models = await getModels();
  return (
    <html lang="en" className={cn("dark font-sans", inter.variable, mono.variable)}>
      <body className="min-h-svh bg-background text-foreground antialiased">
        <Providers>
          <SidebarProvider
            defaultOpen={false}
            style={
              {
                "--sidebar-width": "56px",
                "--sidebar-width-icon": "56px",
              } as React.CSSProperties
            }
          >
            <Rail models={catalogCount(models.data)} routers={1} keys={1} />
            <SidebarInset className="mr-11 min-h-svh">
              {children}
            </SidebarInset>
            <HowToRail />
            <div className="pointer-events-none fixed right-14 bottom-3 z-40 font-mono text-[10px] text-muted-foreground">
              local
            </div>
          </SidebarProvider>
        </Providers>
      </body>
    </html>
  );
}
