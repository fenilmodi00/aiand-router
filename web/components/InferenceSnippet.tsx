"use client";

import { useState } from "react";

const CURL = `curl -X POST "http://127.0.0.1:8000/v1/chat/completions" \\
    -H "Content-Type: application/json" \\
    -H "Authorization: Bearer <YOUR_API_KEY>" \\
    -d '{
  "model": "router/auto",
  "messages": [
    {
      "role": "system",
      "content": "You are a helpful assistant."
    },
    {
      "role": "user",
      "content": "Extract the key people, companies, and locations from this text: \\"Acme Corp hired Jane Doe as CTO on April 11, 2026 in Berlin.\\""
    }
  ],
  "stream": false
}'`;

export function InferenceSnippet() {
  const [label, setLabel] = useState("Copy");
  return (
    <div className="card" id="run-inference">
      <div className="code-head">
        <span>
          Routed through&nbsp;<span className="accent">router/auto</span>
        </span>
        <span className="right">
          <span className="version-pill">
            local&nbsp;<b>GATEWAY</b>
          </span>
          <button
            className="btn btn-sm"
            type="button"
            onClick={() => {
              navigator.clipboard.writeText(CURL).then(() => {
                setLabel("Copied");
                setTimeout(() => setLabel("Copy"), 1400);
              });
            }}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
              <rect x="9" y="9" width="12" height="12" rx="2" />
              <path d="M5 15V5a2 2 0 012-2h10" />
            </svg>
            <span>{label}</span>
          </button>
        </span>
      </div>
      <pre className="code">
        curl -X POST <span className="g">&quot;http://127.0.0.1:8000/v1/chat/completions&quot;</span> \
    -H <span className="g">&quot;Content-Type: application/json&quot;</span> \
    -H <span className="g">&quot;Authorization: Bearer &lt;YOUR_API_KEY&gt;&quot;</span> \
    -d <span className="g">
          {`'{
  "model": "`}
          <span className="o">router/auto</span>
          {`",
  "messages": [
    {
      "role": "system",
      "content": "You are a helpful assistant."
    },
    {
      "role": "user",
      "content": "Extract the key people, companies, and locations from this text: \\"Acme Corp hired Jane Doe as CTO on April 11, 2026 in Berlin.\\""
    }
  ],
  "stream": false
}'`}
        </span>
      </pre>
    </div>
  );
}
