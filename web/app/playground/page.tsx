import Link from "next/link";
import { Playground } from "@/components/Playground";
import { getModels } from "@/lib/api";

export default async function PlaygroundPage() {
  const res = await getModels();
  const models = (res.data?.data ?? []).filter((m) => m.id !== "router/auto");

  return (
    <div className="content">
      <nav className="breadcrumb" aria-label="Breadcrumb">
        <Link className="back" href="/routers/auto" aria-label="Back">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M15 6l-6 6 6 6" />
          </svg>
        </Link>
        <Link href="/routers">Routers</Link>
        <span className="sep">/</span>
        <Link href="/routers/auto">router/auto</Link>
        <span className="sep">/</span>
        <span className="current">Playground</span>
      </nav>
      <Playground models={models} loadError={res.ok ? null : res.error} />
    </div>
  );
}
