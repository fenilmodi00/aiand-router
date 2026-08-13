import Link from "next/link";
import { getOverview } from "@/lib/api";

export default async function RoutersPage() {
  const overview = await getOverview("all");
  const n = overview.data?.candidates.filter((c) => c.enabled).length ?? overview.data?.candidates.length ?? 0;
  const meta = n ? `Router · Auto · ${n} candidates` : "Router · Auto";

  return (
    <div className="content">
      <div className="section-head" style={{ marginTop: 0 }}>
        <div>
          <h2 className="big">Routers</h2>
          <div className="card-sub">Inference routers configured in this workspace.</div>
        </div>
      </div>
      {overview.error && !overview.ok ? (
        <div className="empty" style={{ height: 48, marginBottom: 16 }}>
          Gateway unreachable ({overview.error}). Showing the local router row anyway.
        </div>
      ) : null}
      <div className="table">
        <Link className="router-row" href="/routers/auto">
          <div className="name">router/auto</div>
          <div className="meta">{meta}</div>
          <p className="desc">Routes each request to the cheapest candidate that still meets the quality bar.</p>
          <span className="go">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M9 6l6 6-6 6" />
            </svg>
          </span>
        </Link>
      </div>
    </div>
  );
}
