"use client";

import { useState } from "react";
import type { Candidate, Inference } from "@/lib/types";
import { shortTs } from "@/lib/format";

function qualityCell(row: Inference): string {
  if (row.tests_passed === true) return "pass";
  if (row.tests_passed === false) return "fail";
  if (row.llmaj_score != null) return String(row.llmaj_score);
  return "—";
}

export function InferencesTable({
  rows,
  range,
  q,
  model,
  candidates,
  error,
}: {
  rows: Inference[];
  range: string;
  q: string;
  model: string;
  candidates: Candidate[];
  error?: string | null;
}) {
  const [grid, setGrid] = useState(false);
  return (
    <>
      <form className="toolbar" action="/routers/auto" method="get">
        <input type="hidden" name="range" value={range} />
        <label className="search">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
            <circle cx="11" cy="11" r="7" />
            <path d="M20 20l-3.5-3.5" />
          </svg>
          <input type="search" name="q" defaultValue={q} placeholder="Search inferences..." aria-label="Search inferences" />
        </label>
        <select className="filter" name="model" defaultValue={model} aria-label="Model">
          <option value="">Model</option>
          {candidates.map((c) => (
            <option key={c.id} value={c.id}>
              {c.display_name}
            </option>
          ))}
        </select>
        <button className="btn" type="submit" style={{ height: 40 }}>
          Filter
        </button>
        <span className="view-toggle">
          <button type="button" aria-label="Grid view" className={grid ? "on" : ""} onClick={() => setGrid(true)}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
              <rect x="3" y="3" width="7" height="7" rx="1.5" />
              <rect x="14" y="3" width="7" height="7" rx="1.5" />
              <rect x="3" y="14" width="7" height="7" rx="1.5" />
              <rect x="14" y="14" width="7" height="7" rx="1.5" />
            </svg>
          </button>
          <button type="button" aria-label="List view" className={!grid ? "on" : ""} onClick={() => setGrid(false)}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
              <path d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
        </span>
      </form>
      {grid ? (
        <div className="infer-grid">
          {rows.length === 0 ? (
            <div className="empty" style={{ height: 120, gridColumn: "1 / -1" }}>
              {error ? `Gateway error: ${error}` : "No data matches your filters."}
            </div>
          ) : (
            rows.map((row, i) => (
              <div className="card infer-card" key={`${row.ts}-${i}`}>
                <div className="k">Time</div>
                <div className="v">{shortTs(row.ts)}</div>
                <div className="k" style={{ marginTop: 10 }}>
                  Model
                </div>
                <div className="v">
                  {row.selected || "—"}
                  <div className="muted">{row.path}</div>
                </div>
                <div className="k" style={{ marginTop: 10 }}>
                  Status / cache
                </div>
                <div className="v">
                  {row.status} · {row.cache_hit ? "hit" : "miss"}
                </div>
              </div>
            ))
          )}
        </div>
      ) : (
        <div className="table">
          <table>
            <thead>
              <tr>
                <th>Time</th>
                <th>Model</th>
                <th>Input</th>
                <th className="r">E2E latency</th>
                <th className="r">TTFT</th>
                <th className="r">Tokens</th>
                <th>Status</th>
                <th className="r">Cache</th>
                <th className="r">LLMaJ Score</th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr>
                  <td colSpan={9} className="empty-row">
                    {error ? `Gateway error: ${error}` : "No data matches your filters."}
                  </td>
                </tr>
              ) : (
                rows.map((row, i) => (
                  <tr key={`${row.ts}-${row.selected}-${i}`}>
                    <td>{shortTs(row.ts)}</td>
                    <td>
                      {row.selected || "—"}
                      <div className="muted">
                        {row.path}
                        {row.phase ? ` · ${row.phase}` : ""}
                      </div>
                    </td>
                    <td>{row.tokens_in}</td>
                    <td className="r">{row.latency_ms} ms</td>
                    <td className="r">{row.ttft_ms == null ? "—" : `${row.ttft_ms} ms`}</td>
                    <td className="r">{row.tokens_out}</td>
                    <td>{row.status}</td>
                    <td className="r">{row.cache_hit ? "hit" : "—"}</td>
                    <td className="r">{qualityCell(row)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
