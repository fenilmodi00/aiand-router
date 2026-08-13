import Link from "next/link";
import { KeyPill } from "@/components/KeyPill";
import { maskKey } from "@/lib/api";

export default function KeysPage() {
  const masked = maskKey();
  return (
    <div className="content">
      <div className="section-head" style={{ marginTop: 0 }}>
        <div>
          <h2 className="big">API keys</h2>
          <div className="card-sub">Router gateway key only. This is not AIand org key admin.</div>
        </div>
      </div>
      <div className="card card-pad" style={{ maxWidth: 640 }}>
        <div className="field-head">
          <span className="left">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
              <circle cx="8" cy="15" r="4" />
              <path d="M11 12l9-9M17 4l3 3M14 7l3 3" />
            </svg>
            ROUTER_API_KEY
          </span>
        </div>
        <KeyPill masked={masked} />
        <p className="hint">
          Masked preview of the Next server env var <strong>ROUTER_API_KEY</strong>
          {masked.set ? "" : " (not set)"}. The raw value is not in the client bundle. Copy asks the
          server for it. Point clients at <code>http://127.0.0.1:8000</code> with this key — never{" "}
          <code>AIAND_API_KEY</code>.
        </p>
        <div className="hero-actions" style={{ paddingTop: 24 }}>
          <Link className="btn" href="/routers/auto#run-inference">
            Integrate curl
          </Link>
          <Link className="btn btn-primary" href="/playground">
            Try in playground
          </Link>
        </div>
      </div>
    </div>
  );
}
