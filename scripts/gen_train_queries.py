"""Build datasets/train-queries.jsonl — unpaid coding-agent prompts for teacher/gold/fit.

hint_bin is a stratum prior, not a gold label. The teacher still assigns complexity_bin.
Lengths scale with bin so Rec A (log tokens + phase + tools) has a real signal.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

N = 2000
SEED = 20260813
OUT = Path(__file__).resolve().parents[1] / "datasets" / "train-queries.jsonl"

# Spec margins for sparse-train strata, scaled to N=2000.
BIN_N = {"trivial": 300, "standard": 800, "hard": 600, "frontier": 300}
PHASE_N = {
    "edit": 600,
    "tool": 500,
    "plan": 300,
    "debug": 300,
    "discover": 200,
    "summarize": 100,
}

FILES = [
    "src/stats.ts",
    "src/aiand_router/app.py",
    "src/aiand_router/router.py",
    "src/aiand_router/scorer.py",
    "src/aiand_router/train.py",
    "src/aiand_router/cache.py",
    "src/billing/ledger.go",
    "src/auth/session.rs",
    "src/http/proxy.kt",
    "src/db/migrate.sql",
    "internal/pool/conn.go",
    "pkg/ratelimit/token_bucket.go",
    "lib/parser/jsonl.py",
    "lib/crypto/hkdf.ts",
    "apps/web/src/hooks/useReplay.ts",
    "apps/web/src/pages/Replay.tsx",
    "services/gateway/main.go",
    "services/worker/consumer.py",
    "crates/router/src/pick.rs",
    "crates/router/src/eligible.rs",
    "backend/src/main/java/SpendLog.java",
    "backend/src/main/java/EligibleModels.java",
    "mobile/ios/RouterClient.swift",
    "mobile/android/Gateway.kt",
    "infra/terraform/cache.tf",
    "infra/k8s/gateway.yaml",
    "config/models.yaml",
    "config/tasks.yaml",
    "tests/test_gateway.py",
    "tests/test_train.py",
    "tests/test_scorer.py",
    "README.md",
    "docs/runbook.md",
    "scripts/rotate_keys.sh",
    "web/src/api/completions.ts",
    "web/src/components/JsonlViewer.tsx",
    "etl/jobs/nightly_fit.py",
    "etl/transforms/redact.py",
    "proto/router.proto",
    "cmd/gateway/main.go",
]

FNS = [
    "parseIsoDate",
    "formatUsd",
    "eligible_models",
    "select_model",
    "featurize",
    "estimate_tokens",
    "request_cache_key",
    "cheapest_above_bar",
    "load_scorer",
    "detect_phase",
    "redact_row",
    "append_jsonl",
    "token_bucket_take",
    "hkdf_expand",
    "parse_sse_chunk",
    "flush_spend",
    "platt_scale",
    "fit_binary",
    "create_app",
    "handle_completions",
]

SYMS = [
    "tmp",
    "userCount",
    "aa_bar",
    "max_regret",
    "p_success",
    "baseline_model_id",
    "trained_selected",
    "needs_tools",
    "complexity_bin",
    "BUDGET_LIMIT_USD",
    "TRAINED_PATH",
    "x-request-id",
    "X-Router-Trained-Would",
    "fallback_declined",
    "scorer_down",
]

ERRS = [
    "AssertionError: expected 2 got 3",
    "ImportError: cannot import name load_scorer",
    "TypeError: Object of type bytes is not JSON serializable",
    "RuntimeError: dictionary changed size during iteration",
    "sqlalchemy.exc.IntegrityError: UNIQUE constraint failed: hops.id",
    "tokio::time::error::Elapsed",
    "java.util.ConcurrentModificationException",
    "panic: runtime error: invalid memory address or nil pointer dereference",
    "error[E0502]: cannot borrow `cache` as mutable because it is also borrowed as immutable",
    "CS8618: Non-nullable field must contain a non-null value when exiting constructor",
    "FATAL: remaining connection slots are reserved for non-replication superuser connections",
    "httpx.ReadTimeout: timed out on /v1/chat/completions",
    "json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)",
    "KeyError: 'p_success'",
    "ValueError: TRAINED_PATH invalid",
]

TOOLS = [
    "read_file",
    "list_files",
    "grep",
    "glob",
    "read_file on config/models.yaml",
    "list_files on src/aiand_router",
    "grep for eligible_models",
    "read_file on CONTEXT.md",
]


def bag(counts: dict[str, int]) -> list[str]:
    out: list[str] = []
    for k, n in counts.items():
        out.extend([k] * n)
    return out


def snippet_py(i: int, n: int) -> str:
    lines = [
        "from __future__ import annotations",
        "import json",
        "from pathlib import Path",
        f"# shard {i}",
        "",
        "def load_rows(path: Path):",
        "    for line in path.read_text(encoding='utf-8').splitlines():",
        "        if line.strip():",
        "            yield json.loads(line)",
        "",
    ]
    for k in range(max(2, n)):
        lines += [
            f"def handle_{i}_{k}(row: dict, bar: float) -> str | None:",
            f"    p = float((row.get('p_success') or {{}}).get('flash', 0))",
            "    if p < bar:",
            "        return None",
            f"    return row.get('model_id') or 'fallback-{k}'",
            "",
        ]
    return "\n".join(lines)


def snippet_ts(i: int, n: int) -> str:
    lines = [f"export type Hop{i} = {{ model: string; path: 'rules' | 'shadow' | 'trained' }}", ""]
    for k in range(max(2, n)):
        lines += [
            f"export function pick{i}_{k}(p: Record<string, number>, t: number, r: number): string {{",
            "  const ids = Object.keys(p).sort((a, b) => p[b] - p[a])",
            "  const top = p[ids[0]] ?? 0",
            "  for (const id of ids) {",
            "    if ((p[id] ?? 0) >= t && top - (p[id] ?? 0) <= r) return id",
            "  }",
            "  return 'fallback'",
            "}",
            "",
        ]
    return "\n".join(lines)


def snippet_go(i: int, n: int) -> str:
    lines = ["package router", "", "import \"sync\"", "", f"type shard{i} struct {{ mu sync.Mutex; n int }}", ""]
    for k in range(max(2, n)):
        lines += [
            f"func (s *shard{i}) Take{k}(cost float64) error {{",
            "    s.mu.Lock()",
            "    defer s.mu.Unlock()",
            "    if float64(s.n)+cost > 15 { return ErrBudget }",
            "    s.n++",
            "    return nil",
            "}",
            "",
        ]
    return "\n".join(lines)


def snippet_rs(i: int, n: int) -> str:
    lines = ["use std::collections::HashMap;", "", f"pub struct Pick{i} {{ pub bar: f64 }}", ""]
    for k in range(max(2, n)):
        lines += [
            f"impl Pick{i} {{",
            f"    pub fn cheapest_{k}(&self, p: &HashMap<String, f64>) -> Option<String> {{",
            "        p.iter().filter(|(_, v)| **v >= self.bar).min_by(|a, b| a.1.partial_cmp(b.1).unwrap()).map(|(k, _)| k.clone())",
            "    }",
            "}",
            "",
        ]
    return "\n".join(lines)


def snippet_sql(i: int) -> str:
    return f"""CREATE TABLE hops_{i} (
  id TEXT PRIMARY KEY,
  path TEXT NOT NULL CHECK (path IN ('rules','shadow','trained')),
  selected TEXT NOT NULL,
  complexity_bin TEXT,
  savings_usd NUMERIC,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX hops_{i}_path ON hops_{i}(path, created_at DESC);
"""


def snippet_stack(err: str, file: str, fn: str, i: int) -> str:
    return f"""Traceback (most recent call last):
  File "{file}", line {40 + (i % 80)}, in {fn}
    return inner(row)
  File "src/aiand_router/scorer.py", line {12 + (i % 40)}, in score_eligible
    x = featurize(phase, needs_tools, tokens)
{err}
Request id: req_{i:04d}
X-Router-Path: shadow
"""


def blob(bin_: str, i: int, rng: random.Random) -> str:
    if bin_ == "trivial":
        return ""
    kind = rng.choice(["py", "ts", "go", "rs", "sql", "stack"])
    if bin_ == "standard":
        n = rng.randint(2, 4)
    elif bin_ == "hard":
        n = rng.randint(6, 12)
    else:
        n = rng.randint(14, 22)
    if kind == "py":
        body = snippet_py(i, n)
    elif kind == "ts":
        body = snippet_ts(i, n)
    elif kind == "go":
        body = snippet_go(i, n)
    elif kind == "rs":
        body = snippet_rs(i, n)
    elif kind == "sql":
        body = snippet_sql(i) + "\n" + snippet_py(i, n // 2)
    else:
        body = snippet_stack(rng.choice(ERRS), rng.choice(FILES), rng.choice(FNS), i)
        if bin_ in {"hard", "frontier"}:
            body += "\n" + snippet_py(i, n)
    return f"\n\nCurrent code / context:\n```\n{body}\n```"


def trivial(phase: str, i: int, rng: random.Random) -> str:
    f, fn, a, b = rng.choice(FILES), rng.choice(FNS), rng.choice(SYMS), rng.choice(SYMS)
    cores = [
        f"Rename the variable {a} to {b} in {f} and leave behavior unchanged.",
        f"Add a one-line docstring to function {fn} explaining that it returns UTC.",
        f"Fix the typo 'recieve' to 'receive' in {f}. Do not change anything else.",
        f"What files exist under src/aiand_router/? List paths only.",
        f"Add max_tokens=64 to the gold complete() body in {f} and stop.",
        f"Print the type of {fn}'s return value. No patch.",
        f"Change the default of TRAINED_PATH comment in {f} from off to shadow. Comment only.",
        f"Replace tabs with 4 spaces in {f}. No logic changes.",
        f"Export {fn} from the module index. Do not change its body.",
        f"Add `# noqa: ARG001` to the unused argument on {fn}.",
        f"Quote the first line of {f}. Nothing else.",
        f"Lowercase the log label '{a}' in {f}.",
        f"Delete the unused import of json in {f} if it is truly unused.",
        f"Rename test test_{fn} to test_{fn}_ok. Keep assertions.",
        f"Add a trailing newline to {f} if missing.",
    ]
    return rng.choice(cores)


def standard(phase: str, i: int, rng: random.Random) -> str:
    f, fn, err = rng.choice(FILES), rng.choice(FNS), rng.choice(ERRS)
    cores = [
        f"Add a TypeScript function {fn} that formats a number as USD with two decimals.",
        f"Write a Python helper that reads a .jsonl file and yields parsed objects, skipping blank lines.",
        f"Add input validation so BUDGET_LIMIT_USD below 0 is treated as 0 in the spend log.",
        f"Parse a JSON object of usage tokens and return prompt_tokens + completion_tokens as an int.",
        f"Write a regex that matches aiand model ids like org/name with a slash and no spaces.",
        f"Add an optional x-request-id header that is copied onto the JSONL row in {f}.",
        f"pytest says {err}. Where would you look first in {f}?",
        f"Implement {fn} to return the cheapest model id whose p_success >= threshold.",
        f"Add a unit test that tools-present requests never include a no-tools model in p_success keys.",
        f"Cache GET /health for 5 seconds in-process. Do not add Redis.",
        f"Make {fn} reject empty prompt strings after stripping, returning 400.",
        f"Add retries=1 only on 429 from the upstream provider in {f}.",
        f"Redact Authorization and api_key keys before append_jsonl writes {f}.",
        f"Convert {fn} from a list scan to a dict lookup keyed by model id.",
        f"Add a SQL check constraint that path is one of rules, shadow, trained.",
        f"Write a Go function that atomically increments spend.txt by a float64 usd amount.",
        f"Add a FastAPI /healthz alias that returns the existing /health JSON.",
        f"Parse SSE lines starting with data: and yield JSON chunks, ignoring comments.",
        f"Add env AIAND_TRAIN check: if not 1, the train CLI must refuse before any HTTP.",
        f"Implement Platt a, b application: sigmoid(a * logit + b) with logit clamped to [-30, 30].",
        f"Given {err} on {fn}, name the likely off-by-one and the one-line fix.",
        f"Add max_regret filtering: drop ids where top_p - p > max_regret, then pick cheapest.",
        f"Write a YAML snippet for trained_effort medium: threshold 0.10, max_regret 0.20.",
        f"Create a request cache key from model + messages content, sensitive to message order.",
        f"Add a Python context manager that records elapsed_ms onto the JSONL row.",
        f"Port {fn} from callbacks to async def without changing the public signature.",
        f"Add a CSS class for scorer_down banners. No JS.",
        f"Write a shell one-liner that greps data/requests.jsonl for path=shadow and counts rows.",
        f"Validate hint_bin is one of trivial|standard|hard|frontier; skip the line if not.",
        f"Add CORS allow-list for localhost:3000 on /v1/chat/completions only.",
    ]
    return rng.choice(cores)


def hard(phase: str, i: int, rng: random.Random) -> str:
    f, fn, err = rng.choice(FILES), rng.choice(FNS), rng.choice(ERRS)
    cores = [
        f"Refactor {fn} so effort=low still runs hard constraints but uses the Scorer. Keep the public signature.",
        f"Plan how to add streaming tool-calls without buffering the whole upstream SSE in memory.",
        f"A client sends tools and json_schema together. Trace which hard constraint drops which models.",
        f"Find all call sites that write data/requests.jsonl and check they redact authorization.",
        f"Implement cheapest-above-bar given p_success, threshold, and max_regret. Return the model id or fallback.",
        f"Shadow headers show X-Router-Trained-Would equal to X-Router-Model on every request. List three causes.",
        f"Plan a migration from intercept-only mean gold to per-model logistic + Platt without changing the HTTP contract.",
        f"The unit tests fail with {err} after adding a Scorer artifact. Bisect {f} and {fn}.",
        f"Make TRAINED_PATH=trained serve the cheapest-above-bar pick while rules stay fallback on scorer_down.",
        f"Add an in-process feature vector using only phase family, tools flag, and log tokens. No embeddings.",
        f"Race: two gold complete() calls increment spend.txt. Make SpendLog safe without a DB.",
        f"Eligible set with tools present must not include a no-tools model in candidates or p_success keys. Prove it with a test.",
        f"Design decline: if no survivor clears threshold, serve fallback, rule=fallback_declined, HTTP 200.",
        f"K3 must not appear in $100 gold smoke cells. Enforce in run_gold and a test.",
        f"Teacher must exclude qwen/, moonshotai/, and deepseek-ai/ ids. Escalate Motif → GLM, temperature 0.",
        f"When the teacher returns prose instead of JSON, store unlabeled=true. Never invent a bin.",
        f"New catalog id without a dense gold slice must stay rules-only for live P(success).",
        f"Savings vs most_expensive_eligible only. K3 is baseline id only when it is eligible.",
        f"Map flashlight phases onto complexity bins. Bins must not become the pick.",
        f"Implement gold-where-present + silver regularizer on unobserved cells only. Missing ≠ 0.",
        f"Add mtime reload of scorer.json optional. Default stays load-once at process start.",
        f"A calibrated P(success) of 0.9 that is really 0.4 will pick too-cheap models. What JSONL observable reveals that?",
        f"Thread effort knobs from x-routing-effort through trained_effort YAML, namespaced away from rules max_regret: 8.",
        f"On-call: spend.txt hit BUDGET_LIMIT_USD mid-gold. What does the CLI do next, and what must stay unlabeled?",
        f"Keep the learned highest-AA stub from replacing Rec A even if learned_wins.json is on.",
        f"Fix a deadlock in the request cache: lock order is cache then spend, but gold inverts it under --dense.",
        f"Streaming: if the upstream SSE stalls after a tool_call delta, do not retry with a second provider call.",
        f"Security review {f}: confirm JSONL redaction strips bearer tokens, cookies, and api_key nested keys.",
        f"Multi-file: split {fn} so eligible_models stays pure and select_model owns cheapest-above-bar.",
        f"Debug {err} when tools and response_format json_schema are both set. Quote the constraint that drops Flash.",
    ]
    return rng.choice(cores)


def frontier(phase: str, i: int, rng: random.Random) -> str:
    cores = [
        "Design a flywheel: ingest production JSONL nightly, refit the Scorer, keep not_spec_floors until a promotion gate passes. Name the splits and what must never enter Platt.",
        "Propose Rec A vs a future Rec B with embeddings. v1 must stay features-only on the hop, <10ms, no live chat teacher.",
        "How should a new catalog id without a dense gold slice behave on path=trained? Cite the hop spec rule and the operator rollback env.",
        "Write an operator runbook: shadow for a day, grep path=, then TRAINED_PATH=trained. Include scorer_down and budget hit.",
        "Specify production floors you will NOT claim for this $100 smoke: n=4000 sparse, n≥300 retune, SWE-bench Verified, Terminal-Bench. What does not_spec_floors mean on the artifact?",
        "Lock-free cheapest-above-bar under concurrent hops. Allowed: one mutex around Decision write. Not allowed: stopping the event loop.",
        "Adversarial client sends a 200k-token prompt with tools and json_schema. Trace eligible set, token feature, budget, and which path is recorded if the Scorer times out.",
        "Calibrate without leaking silver into Platt. Gold-only logits. Silver regularizer only on unobserved (prompt, model) cells. Write the fit steps.",
        "Multi-region spend.txt is not a source of truth. Design a later upgrade to per-account ledgers without changing /v1/chat/completions.",
        "Map RouterBench-style matrices onto this catalog. Why MBPP/MMLU rows must not be the coding-agent train set, and what public dumps are allowed as style only.",
        "Implement a promotion gate that is documented, not executed this cycle: Verified/Lite as eval, never as train. Collision-filter any query that looks like a canary.",
        "Huge ambiguous repo: the client pasted 12 services and asked to 'make routing smarter'. Produce a plan that keeps rules as fallback and refuses a Pioneer dashboard clone.",
        "Novel algorithm: replace logistic Rec A with a GBDT + Platt in-process. Same Decision contract. Prove scorer_down still serves rules with no fake confidence.",
        "Cross-cutting: nightly refit, catalog add, and a pinned model id bypass must all coexist. Write invariants and tests for each.",
        "SWE-Verified-class task: localize a flaky race across gateway, spend log, and SSE proxy, then ship the smallest fix that preserves the HTTP contract.",
        "Threshold retune split must be disjoint from smoke gold. Describe how you would carve it later without touching this $100 cycle's weights.",
        "Bloom_level may exist on teacher rows only. Keep it off live headers and Decision. Show the leak path if someone copies silver onto JSONL hops.",
        "If shadow trained-would equals rules on 99% of hops, is the Scorer broken, the eligible set tiny, or the feature vector constant? List observables.",
        "Design missing-cell handling when Flash has gold but a new cheap model does not. Unobserved ≠ 0. Live P(success) must not unstick on silver.",
        "Write the cheapest-above-bar proof: threshold, max_regret, fallback_declined, K3 eligible-only baseline, tools hard-constraint. One page, no dashboard.",
    ]
    extra = [
        "Constraints: Windows/PowerShell; default BUDGET_LIMIT_USD stays 15 in code; smoke operator may set 100.",
        "Do not invent a savings percentage. Savings vs most_expensive_eligible only.",
        "Clients keep talking to /v1/chat/completions. No new protocol.",
        "Do not train on Terminal-Bench canaries or copy SWE-bench Verified problem statements.",
        "Teacher: Motif-3 then GLM 5.2, temperature 0, strict json_schema teacher_label.",
    ]
    return rng.choice(cores) + " " + rng.choice(extra)


def wrap_phase(phase: str, core: str, i: int, rng: random.Random) -> str:
    tool = rng.choice(TOOLS)
    f = rng.choice(FILES)
    if phase == "tool":
        opens = [
            f"Given tools, call {tool} then stop.",
            f"You have tools. Open {f} with read_file, then stop after the tool result.",
            f"Call the tools needed to inspect {f}. Do not patch.",
            f"Use grep/list_files only. Quote one matching line from {f}.",
        ]
        return rng.choice(opens) + "\n\n" + core
    if phase == "discover":
        opens = [
            "Find where this lives and name the file. Do not propose a patch yet.",
            "Locate every call site. List paths only.",
            "Repository discovery: which modules own this behavior?",
        ]
        return rng.choice(opens) + "\n\n" + core
    if phase == "plan":
        opens = [
            "Plan the smallest change. Do not write the full patch yet.",
            "Sketch the approach in bullets. Name files you would touch.",
            "Write a short plan with risks. No code dump.",
        ]
        return rng.choice(opens) + "\n\n" + core
    if phase == "debug":
        opens = [
            "Debug this failure. Name the likely cause before a patch.",
            "On-call: what broke, what the client sees, what not to do.",
            "Trace the hop. Which constraint or scorer field is wrong?",
        ]
        return rng.choice(opens) + "\n\n" + core
    if phase == "summarize":
        opens = [
            "Summarize for an on-call engineer in three bullets. No patch.",
            "Summarize this module in two sentences.",
            "Write a short operator note. No implementation.",
        ]
        return rng.choice(opens) + "\n\n" + core
    # edit: sometimes a light steer toward a patch
    if i % 5 == 0:
        return "Implement the change. Keep the public signature.\n\n" + core
    return core


def make_prompt(phase: str, bin_: str, i: int, rng: random.Random) -> str:
    if bin_ == "trivial":
        core = trivial(phase, i, rng)
    elif bin_ == "standard":
        core = standard(phase, i, rng)
    elif bin_ == "hard":
        core = hard(phase, i, rng)
    else:
        core = frontier(phase, i, rng)
    prompt = wrap_phase(phase, core, i, rng)
    extra = blob(bin_, i, rng)
    if extra:
        prompt += extra
    if bin_ == "frontier":
        prompt += (
            f"\n\nAcceptance: HTTP contract unchanged; path in {{rules,shadow,trained}}; "
            f"no fake P(success) on scorer_down; query id q-{i:04d}."
        )
    elif bin_ == "hard" and i % 2 == 0:
        prompt += f"\n\nKeep tests on the ASGI seam with a fake provider. Query id q-{i:04d}."
    else:
        prompt += f"\nQuery id q-{i:04d}."
    return prompt


def needs_tools_flags(phases: list[str], rng: random.Random) -> list[bool]:
    flags = [p == "tool" for p in phases]
    need = 1500 - sum(flags)
    extras = [i for i, p in enumerate(phases) if p != "tool"]
    rng.shuffle(extras)
    for i in extras[:need]:
        flags[i] = True
    return flags


def main() -> None:
    rng = random.Random(SEED)
    bins = bag(BIN_N)
    phases = bag(PHASE_N)
    rng.shuffle(bins)
    rng.shuffle(phases)
    tools = needs_tools_flags(phases, rng)
    seen: set[str] = set()
    rows: list[dict] = []
    for i, (phase, bin_, nt) in enumerate(zip(phases, bins, tools)):
        prompt = make_prompt(phase, bin_, i, rng)
        n = 0
        while prompt in seen:
            n += 1
            prompt = make_prompt(phase, bin_, i, rng) + f"\nvariant {n}."
        seen.add(prompt)
        rows.append({"prompt": prompt, "phase": phase, "hint_bin": bin_, "needs_tools": nt})
    rng.shuffle(rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    from collections import Counter

    bc = Counter(r["hint_bin"] for r in rows)
    pc = Counter(r["phase"] for r in rows)
    tc = Counter(bool(r["needs_tools"]) for r in rows)
    lens = {}
    for b in BIN_N:
        xs = [len(r["prompt"]) for r in rows if r["hint_bin"] == b]
        lens[b] = (min(xs), sorted(xs)[len(xs) // 2], max(xs))
    print(f"wrote {len(rows)} -> {OUT}")
    print("hint_bin", dict(bc))
    print("phase", dict(pc))
    print("needs_tools", dict(tc))
    print("prompt_chars min/med/max by bin", lens)


if __name__ == "__main__":
    main()
