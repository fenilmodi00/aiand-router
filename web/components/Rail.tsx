"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

const ICONS = {
  overview: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <rect x="3" y="3" width="7" height="7" rx="1.5" />
      <rect x="14" y="3" width="7" height="7" rx="1.5" />
      <rect x="3" y="14" width="7" height="7" rx="1.5" />
      <rect x="14" y="14" width="7" height="7" rx="1.5" />
    </svg>
  ),
  routers: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <circle cx="5" cy="12" r="2" />
      <circle cx="19" cy="6" r="2" />
      <circle cx="19" cy="18" r="2" />
      <path d="M7 11l10-4M7 13l10 4" />
    </svg>
  ),
  models: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M12 2l9 5-9 5-9-5 9-5z" />
      <path d="M3 12l9 5 9-5" />
      <path d="M3 17l9 5 9-5" />
    </svg>
  ),
  keys: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <circle cx="8" cy="15" r="4" />
      <path d="M11 12l9-9M17 4l3 3M14 7l3 3" />
    </svg>
  ),
  usage: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M4 20V10M10 20V4M16 20v-8M22 20H2" />
    </svg>
  ),
  settings: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <circle cx="12" cy="12" r="3" />
      <path d="M19 12a7 7 0 00-.14-1.4l2-1.55-2-3.46-2.35.94a7 7 0 00-2.42-1.4L13.7 2h-3.4l-.39 2.63a7 7 0 00-2.42 1.4l-2.35-.94-2 3.46 2 1.55A7 7 0 005 12" />
    </svg>
  ),
};

function Item({
  href,
  label,
  icon,
  active,
  badge,
}: {
  href?: string;
  label: string;
  icon: ReactNode;
  active?: boolean;
  badge?: number;
}) {
  const className = `rail-item${active ? " active" : ""}`;
  const inner = (
    <>
      {icon}
      {badge != null && badge > 0 ? <span className="rail-badge">{badge}</span> : null}
    </>
  );
  if (!href) {
    return (
      <span className={className} aria-label={label} title={label}>
        {inner}
      </span>
    );
  }
  return (
    <Link className={className} href={href} aria-label={label} title={label}>
      {inner}
    </Link>
  );
}

export function Rail({
  routers = 0,
  models = 0,
  keys = 0,
}: {
  routers?: number;
  models?: number;
  keys?: number;
}) {
  const path = usePathname();
  const onRouters = path === "/routers" || path.startsWith("/routers/");
  return (
    <nav className="rail" aria-label="Primary">
      <Link className="logo" href="/routers" aria-label="Home">
        A
      </Link>
      <Item href="/routers" label="Overview" icon={ICONS.overview} />
      <Item href="/routers" label="Routers" icon={ICONS.routers} active={onRouters} badge={routers} />
      <Item href="/models" label="Models" icon={ICONS.models} active={path === "/models"} badge={models} />
      <Item href="/keys" label="API keys" icon={ICONS.keys} active={path === "/keys"} badge={keys} />
      <Item href="/usage" label="Usage" icon={ICONS.usage} active={path === "/usage"} />
      <div className="spacer" />
      <Item label="Settings" icon={ICONS.settings} />
      <span className="rail-item collapse" aria-label="Collapse sidebar">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
          <path d="M15 6l-6 6 6 6" />
        </svg>
      </span>
    </nav>
  );
}
