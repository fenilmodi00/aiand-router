import { Inter, JetBrains_Mono } from "next/font/google";
import type { Metadata } from "next";
import { catalogCount, getModels } from "@/lib/api";
import { HowToRail } from "@/components/HowToRail";
import { Rail } from "@/components/Rail";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });
const mono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-mono" });

export const metadata: Metadata = {
  title: "Routers · AIand",
  description: "Local operator console for router/auto",
};

export const dynamic = "force-dynamic";

export default async function RootLayout({ children }: LayoutProps<"/">) {
  const models = await getModels();
  return (
    <html lang="en">
      <body className={`${inter.className} ${mono.variable}`}>
        <Rail models={catalogCount(models.data)} routers={1} keys={1} />
        <HowToRail />
        <div className="page">{children}</div>
        <div className="watermark">local</div>
      </body>
    </html>
  );
}
