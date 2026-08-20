#!/usr/bin/env python
"""Build spec-scale query pool with deterministic split manifest.

Generates data/queries_spec.jsonl (~4000 rows) and data/split_manifest.json.
No aiand credits, no network, no src/ edits.

Spec margins (from .scratch/trained-router/spec.md):
  bin:     trivial 15% / standard 40% / hard 30% / frontier 15%
  tools:   present 75% / absent 25%
  phase:   edit 30% / tool 25% / plan 15% / debug 15% / discover 10% / summarize 5%
  occupied-stratum floor >= 20

Splits (deterministic shuffle seed=0, then slice):
  sparse-train:       pool - 900  (feeds T11 teacher + T12 sparse gold)
  dense/cal:          300          (feeds T13)
  tune:               300          (feeds T14)
  promotion-holdout:  300          (feeds T18)
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POOL_OUT = ROOT / "data" / "queries_spec.jsonl"
MANIFEST_OUT = ROOT / "data" / "split_manifest.json"

BIN_FRAC = {"trivial": 0.15, "standard": 0.40, "hard": 0.30, "frontier": 0.15}
PHASE_FRAC = {
    "edit": 0.30,
    "tool": 0.25,
    "plan": 0.15,
    "debug": 0.15,
    "discover": 0.10,
    "summarize": 0.05,
}
TOOLS_FRAC = {True: 0.75, False: 0.25}
STRATUM_FLOOR = 20
TARGET_N = 4000
HOLDOUT_PER_SPLIT = 300
SEED = 0

# --- prompt templates per (bin, phase) ---

_TEMPLATES: dict[tuple[str, str], list[str]] = {
    # trivial
    ("trivial", "discover"): [
        "Find all Python files in the src/ directory that import os.path.",
        "List the functions in utils.py that start with 'get_'.",
        "Show me the imports at the top of main.py.",
        "Find all TODO comments in the codebase.",
        "Which files reference the config variable DEBUG?",
    ],
    ("trivial", "plan"): [
        "I need to rename a variable from 'cnt' to 'count' across the module. Outline the steps.",
        "Plan adding a docstring to the parse_input function.",
        "What's the minimal change to fix this trailing newline issue in output.txt?",
        "I want to update the README to mention Python 3.12. What should I change?",
        "Plan: move the helper function is_valid closer to its only caller.",
    ],
    ("trivial", "edit"): [
        "Rename the variable 'cnt' to 'count' in parser.py.",
        "Add a docstring to the function `def parse_input(s):` that says 'Parse input string into tokens.'",
        "Fix the typo in the error message: 'recieved' should be 'received'.",
        "Add a trailing newline to the end of config.py.",
        "Change the constant MAX_RETRIES from 3 to 5.",
        "Update the comment on line 42 to reflect the new parameter name.",
        "Remove the unused import 'from os import path' in helpers.py.",
        "Add type hint `-> str` to the function get_name.",
    ],
    ("trivial", "tool"): [
        "Run `git status` and show me the output.",
        "Execute `ls -la src/` to list the source directory.",
        "Run `python -m pytest tests/test_basic.py -q` and show results.",
        "Run `grep -r 'TODO' src/` to find all TODO comments.",
        "Execute `git log --oneline -5` to see recent commits.",
    ],
    ("trivial", "debug"): [
        "I got an ImportError: No module named 'requests'. What's wrong?",
        "The script prints 'None' instead of the expected value. Where should I look?",
        "Why does `len([])` return 0? I expected 1.",
        "I see a SyntaxError on line 10. It's a missing colon after the if statement.",
        "The test fails with AssertionError but the assertion looks correct. What's the issue?",
    ],
    ("trivial", "summarize"): [
        "Summarize what the function `validate_email` does in one sentence.",
        "Write a one-line description of the config.py module.",
        "What does the `normalize_path` helper return?",
        "Give me a brief summary of the changes in the last commit.",
        "Describe what the `clean_input` function does.",
    ],
    # standard
    ("standard", "discover"): [
        "Explore the project structure and identify the main entry points and their dependencies.",
        "Find all API endpoint definitions in the codebase and list their HTTP methods and paths.",
        "Trace the data flow from the request handler to the database layer.",
        "Identify all places where environment variables are read and list which ones are required.",
        "Map out the class hierarchy starting from BaseModel and list all subclasses.",
        "Find all database migration files and describe what each migration does.",
        "Locate all test fixtures and explain what data they set up.",
        "Search for all uses of the deprecated `json.loads` without error handling and list them.",
    ],
    ("standard", "plan"): [
        "Plan the implementation of a new REST endpoint POST /api/users that creates a user with email validation.",
        "Design the approach for adding pagination to the existing list endpoint. Consider offset vs cursor-based.",
        "Outline the steps to migrate from SQLite to PostgreSQL, including schema changes and data migration.",
        "Plan adding input validation using Pydantic models to all existing API endpoints.",
        "Design a caching layer for the get_user_profile function using Redis.",
        "Plan the refactoring of the monolithic auth.py into separate modules: tokens.py, sessions.py, permissions.py.",
        "Outline how to add structured logging to all service-layer functions.",
        "Design a rate limiting middleware for the API. Consider per-IP and per-user limits.",
    ],
    ("standard", "edit"): [
        "Implement a function `def paginate(items: list, page: int, per_page: int) -> list` that returns the items for the given page.",
        "Add a new endpoint POST /api/users that accepts a JSON body with name and email, validates the email format, and returns 201 on success.",
        "Write a function `def merge_configs(base: dict, override: dict) -> dict` that deep-merges two config dictionaries.",
        "Implement a retry decorator that retries a function up to 3 times with exponential backoff on ConnectionError.",
        "Add input validation to the update_user endpoint: name must be non-empty, email must match a regex, age must be 0-120.",
        "Write a function `def format_duration(seconds: int) -> str` that converts seconds to '1h 2m 3s' format.",
        "Implement a simple in-memory cache with TTL support: `class TTLCache:` with get, set, and delete methods.",
        "Add a middleware that logs each request's method, path, status code, and duration in JSON format.",
        "Write a function `def deduplicate(items: list[dict], key: str) -> list[dict]` that removes duplicates by the given key.",
        "Implement `def chunk(iterable, size)` that yields chunks of the given size from any iterable.",
    ],
    ("standard", "tool"): [
        "Run the test suite with `python -m pytest tests/ -v --tb=short` and report which tests pass and which fail.",
        "Execute `git diff HEAD~3` and summarize the changes made in the last 3 commits.",
        "Run `python -m mypy src/ --strict` and list all type errors found.",
        "Execute the linter `ruff check src/` and fix all reported issues.",
        "Run `docker compose up -d` and verify all services are healthy by checking their health endpoints.",
        "Execute `python -m pytest tests/test_api.py -k test_create_user --cov=api --cov-report=term-missing` and report coverage.",
        "Run `git blame src/models.py` for the validate_email function and show who last modified each line.",
        "Execute `pip-audit` and list any known vulnerabilities in the installed dependencies.",
    ],
    ("standard", "debug"): [
        "The API returns 500 when creating a user with a duplicate email. The error is an unhandled IntegrityError. Fix it to return 409 instead.",
        "Tests are failing intermittently with a race condition: two tests modify the same fixture and sometimes interfere. Identify and fix the issue.",
        "The celery worker crashes with a SerializationError when processing large payloads. Diagnose the root cause.",
        "Memory usage grows steadily during long-running batch processing. Find the leak and propose a fix.",
        "The login endpoint returns 401 even with correct credentials. Trace through the auth flow and find the bug.",
        "A TypeError occurs when calling process_data(None) — the function doesn't handle None input. Add a guard and a meaningful error.",
        "The migration script fails on PostgreSQL but works on SQLite. The issue is a column type mismatch. Diagnose and fix.",
        "Tests pass locally but fail in CI. The difference is the Python version (3.11 vs 3.12). Find the incompatible code.",
    ],
    ("standard", "summarize"): [
        "Summarize the changes in this pull request: what was added, what was modified, and what was the motivation.",
        "Write a changelog entry for the v2.3.0 release based on the git log since v2.2.0.",
        "Describe the architecture of the authentication system: how tokens are issued, validated, and refreshed.",
        "Summarize the key findings from the performance profiling run. Which functions are the bottlenecks?",
        "Write a brief technical design doc for the new pagination feature: what it does, how it works, and what changed.",
    ],
    # hard
    ("hard", "discover"): [
        "Map the entire call graph of the request processing pipeline: from HTTP handler through middleware, service layer, to database. Identify all side effects.",
        "Trace the lifecycle of a background task from submission to completion. Identify all failure modes and recovery paths.",
        "Analyze the dependency graph between modules. Identify circular dependencies and propose a decoupling strategy.",
        "Find all code paths that can trigger a database write. List them with their transaction boundaries and isolation levels.",
        "Audit the codebase for all uses of global mutable state. List each instance and assess thread safety.",
        "Map all event handlers and their execution order. Identify which handlers can fire concurrently and which cannot.",
    ],
    ("hard", "plan"): [
        "Design a migration from a monolithic synchronous API to an async architecture. Consider connection pooling, transaction management, and backward compatibility.",
        "Plan the implementation of a distributed locking mechanism for the job scheduler. Consider failure modes, lease renewal, and deadlock prevention.",
        "Design a multi-tenant data isolation strategy. Compare schema-per-tenant vs row-level security vs separate databases. Recommend one with justification.",
        "Plan a refactoring of the event system from callback-based to an event bus pattern. Identify all subscribers that need migration.",
        "Design a comprehensive testing strategy for the distributed cache layer: unit, integration, and chaos testing. Include failure injection scenarios.",
        "Plan the decomposition of the 2000-line models.py into focused modules. Identify seams, dependency order, and migration steps.",
    ],
    ("hard", "edit"): [
        "Refactor the request handler to use the strategy pattern instead of a 200-line if/elif chain. Extract each branch into a separate strategy class with a common interface.",
        "Implement a connection pool with health checks, automatic recovery, and configurable retry policies. Include connection lifecycle management.",
        "Rewrite the data export pipeline to use streaming instead of loading everything into memory. Handle backpressure and partial failure recovery.",
        "Implement a distributed rate limiter using Redis with sliding window semantics. Handle clock drift and Redis failover.",
        "Add comprehensive error handling to the async task queue: dead letter queues, retry with jitter, and circuit breaker for downstream failures.",
        "Refactor the authentication middleware to support multiple auth schemes (JWT, API key, OAuth) with a clean extension point for new schemes.",
        "Implement a transactional outbox pattern for reliable event publishing alongside database writes.",
        "Rewrite the CSV parser to handle streaming, quoted fields with embedded newlines, and encoding detection. Add fuzzing tests.",
    ],
    ("hard", "tool"): [
        "Run the full integration test suite with `python -m pytest tests/integration/ -x --tb=long -v` against the staging database. Capture and analyze all failures.",
        "Execute `python -m cProfile -o profile.out src/main.py` then analyze the profile with pstats to find the top 20 functions by cumulative time.",
        "Run `docker compose -f docker-compose.test.yml up --abort-on-container-exit` and diagnose why the test runner container exits with code 1.",
        "Execute the database migration `alembic upgrade head` on a copy of production data and verify no data loss. Roll back if issues are found.",
        "Run `python -m pytest tests/ --cov=src --cov-report=html --cov-fail-under=80` and generate the coverage report. Identify uncovered critical paths.",
        "Execute `k6 run load_test.js` against the staging API and analyze the p95 latency and error rate under load.",
    ],
    ("hard", "debug"): [
        "A deadlock occurs in the job scheduler when two workers try to acquire the same lock. The traceback shows a circular wait between the task queue and the notification service. Diagnose and fix.",
        "The application crashes with a segfault when processing certain PDF files. The crash happens in a C extension. Use the core dump to identify the root cause and propose a fix.",
        "Memory usage grows by 50MB per hour under production load. The heap profiler shows retained objects in a cache that should be evicted. Find why eviction is not working.",
        "An intermittent AssertionError in the async pipeline occurs roughly 1 in 1000 runs. The assertion checks an invariant that should always hold. Trace the race condition.",
        "The API latency doubled after the last deployment. The diff includes a new ORM query. Diagnose the N+1 query problem and fix it with eager loading.",
        "A deadlock in the database connection pool causes all requests to hang after ~30 minutes. The pool logs show connections not being returned. Find the leak.",
    ],
    ("hard", "summarize"): [
        "Write a post-mortem for the production incident on 2024-01-15: timeline, root cause, impact, and action items. Include the cascade failure analysis.",
        "Summarize the architecture review findings: list all technical debt items, their risk level, and proposed remediation for each.",
        "Write a technical decision record comparing the three caching strategies we evaluated. Include benchmarks, trade-offs, and the final recommendation.",
        "Summarize the security audit results: list all findings by severity, the affected components, and the remediation status for each.",
        "Write a comprehensive design doc for the new event sourcing system: architecture, data model, consistency guarantees, and migration plan.",
    ],
    # frontier
    ("frontier", "discover"): [
        "Analyze the entire codebase architecture and identify the fundamental design decisions that would need to change to support horizontal sharding. Consider all layers.",
        "Map the complete data consistency model across all services. Identify every point where eventual consistency is accepted and every invariant that is enforced synchronously.",
        "Audit the system for all forms of coupling: temporal, spatial, and semantic. Propose a decoupling roadmap that preserves all current invariants.",
        "Trace every path through which untrusted input reaches a database query. Assess the SQL injection surface across all layers including ORM, raw SQL, and stored procedures.",
    ],
    ("frontier", "plan"): [
        "Design a new architecture for the system that supports multi-region active-active deployment with conflict-free replicated data types (CRDTs) for all mutable state. Include a migration plan from the current single-region setup.",
        "Design a promotion gate evaluation framework for the trained router: define the metrics, the statistical tests, the sample size requirements, and the decision criteria for promoting from shadow to live.",
        "Plan the implementation of a self-healing system that automatically detects and recovers from cascading failures. Consider failure detection, blast radius containment, and recovery verification.",
        "Design a novel approach to model routing that uses calibrated P(success) per eligible model with threshold + max_regret policy. Include the training pipeline, calibration, and promotion gate.",
        "Plan a complete re-architecture of the event system to support exactly-once semantics across all downstream consumers without distributed transactions.",
    ],
    ("frontier", "edit"): [
        "Implement a novel routing policy that emits a complexity bin and calibrated P(success) per eligible model, then picks the cheapest model that clears threshold and max_regret. Include the scorer interface and fallback logic.",
        "Design and implement a conflict-free replicated data type (CRDT) for the user preferences model that supports concurrent updates across regions with automatic convergence.",
        "Implement a self-calibrating threshold system that adjusts the P(success) threshold based on observed outcomes using isotonic regression. Include the online learning loop and safety bounds.",
        "Write a proof-of-concept for a bilinear hop model that combines query features with model features to produce per-eligible P(success). Include the training loop and evaluation harness.",
        "Implement a drift canary monitor that tracks escalate rate, Brier skill score, and ECE on production serve hops, and triggers a full retrain when any metric degrades beyond the promotion-gate definitions.",
    ],
    ("frontier", "tool"): [
        "Run a comprehensive chaos engineering experiment: kill the primary database, the Redis cluster, and two API instances simultaneously. Measure recovery time, data loss, and error rates. Document findings.",
        "Execute a full-system load test simulating 10x peak traffic with realistic traffic patterns. Profile every layer and identify the breaking points with detailed metrics.",
        "Run a formal verification pass on the distributed lock implementation using model checking. Enumerate all possible interleavings and verify the mutual exclusion invariant holds.",
        "Execute a complete security penetration test including SQL injection, XSS, CSRF, SSRF, and authentication bypass attempts. Document all findings with reproduction steps.",
    ],
    ("frontier", "debug"): [
        "A subtle data corruption bug manifests only when three specific services process the same entity concurrently across regions. The CRDT should converge but doesn't in this specific case. Diagnose the convergence failure.",
        "The trained router occasionally picks a model that clears threshold but has a systematic bias on a specific query pattern not seen in training. Diagnose the distribution shift and propose a mitigation.",
        "A Heisenbug in the distributed transaction system: the system works under observation (with logging) but fails in production (without logging). The timing change from logging masks a race condition. Find it.",
        "The promotion gate passes on all metrics but the trained router underperforms rules in production by 2pp on escalate rate. The calibration is fine, the threshold is fine. Diagnose the selection-conditioned bias.",
    ],
    ("frontier", "summarize"): [
        "Write a comprehensive proposal-grade spec for a production trained router: include the algorithm, data pipeline, calibration, promotion gate, observability, and catalog drift handling. This is for aiand staff to staff and budget.",
        "Write a research retrospective on the model routing approach: what worked, what didn't, what surprised us, and what we would do differently. Include quantitative results.",
        "Summarize the complete system architecture for a new engineering hire: all services, data flows, consistency models, failure modes, and operational procedures. Include an architecture diagram description.",
        "Write a technical whitepaper on the calibrated P(success) approach to model routing: the theory, the implementation, the evaluation methodology, and the production results.",
    ],
}

# Tools context suffixes appended when needs_tools=True
_TOOLS_SUFFIX = [
    " Use the available file and shell tools as needed.",
    " You have access to file read/write and bash tools.",
    " Use your tools to explore the codebase and verify your work.",
    " You may use shell commands and file operations to complete this task.",
    " Leverage the available development tools to implement and test your solution.",
]

# No-tools suffix for needs_tools=False
_NOTOOLS_SUFFIX = [
    " Provide the solution directly without using any tools.",
    " Answer based on the information given, no tool calls needed.",
    " Respond with the code or analysis directly.",
    " No external tools are needed for this task.",
    " Provide your answer as a direct text response.",
]


def _estimate_tokens(prompt: str) -> int:
    """Same formula as router.estimate_tokens: len(json) // 4."""
    return max(1, len(json.dumps([{"role": "user", "content": prompt}], ensure_ascii=False)) // 4)


def _stratum_target(n: int, bin_frac: float, phase_frac: float, tools_frac: float) -> int:
    raw = round(n * bin_frac * phase_frac * tools_frac)
    return max(STRATUM_FLOOR, raw)


def _generate_queries() -> list[dict]:
    """Generate the full query pool hitting spec margins."""
    queries: list[dict] = []
    qid = 0
    rng = random.Random(SEED)

    for bin_name, bin_frac in BIN_FRAC.items():
        for phase, phase_frac in PHASE_FRAC.items():
            for tools, tools_frac in TOOLS_FRAC.items():
                target = _stratum_target(TARGET_N, bin_frac, phase_frac, tools_frac)
                templates = _TEMPLATES.get((bin_name, phase), [])
                if not templates:
                    continue
                suffixes = _TOOLS_SUFFIX if tools else _NOTOOLS_SUFFIX
                for i in range(target):
                    tmpl = templates[i % len(templates)]
                    suffix = suffixes[(i // len(templates)) % len(suffixes)]
                    # Add variation index to ensure uniqueness
                    prompt = f"{tmpl}{suffix}"
                    if i >= len(templates) * len(suffixes):
                        prompt = f"{tmpl} (variant {i // (len(templates) * len(suffixes)) + 1}){suffix}"
                    qid += 1
                    queries.append({
                        "id": f"q{qid:05d}",
                        "prompt": prompt,
                        "phase": phase,
                        "hint_bin": bin_name,
                        "needs_tools": tools,
                        "tokens": _estimate_tokens(prompt),
                        "source": "synthetic",
                        "instance_id": f"q{qid:05d}",
                    })

    # Deterministic shuffle
    rng.shuffle(queries)
    return queries


def _build_manifest(queries: list[dict]) -> dict:
    """Assign each query to exactly one split. Deterministic: shuffle then slice."""
    n = len(queries)
    holdout = HOLDOUT_PER_SPLIT
    splits = {
        "promotion-holdout": [q["id"] for q in queries[:holdout]],
        "tune": [q["id"] for q in queries[holdout:holdout * 2]],
        "dense/cal": [q["id"] for q in queries[holdout * 2:holdout * 3]],
        "sparse-train": [q["id"] for q in queries[holdout * 3:]],
    }
    return {
        "splits": splits,
        "sizes": {k: len(v) for k, v in splits.items()},
        "total": n,
        "seed": SEED,
    }


def _write_jsonl(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
        encoding="utf-8",
    )


def main() -> int:
    queries = _generate_queries()
    print(f"generated: {len(queries)} queries", flush=True)

    # Stratum histogram
    from collections import Counter
    hist: Counter[tuple[str, str, bool]] = Counter()
    for q in queries:
        hist[(q["hint_bin"], q["phase"], q["needs_tools"])] += 1
    print("stratum_histogram:", flush=True)
    for b in BIN_FRAC:
        for p in PHASE_FRAC:
            for t in (True, False):
                n = hist.get((b, p, t), 0)
                if n:
                    print(f"  bin={b} phase={p} tools={t}: {n}", flush=True)

    # Margin check
    n = len(queries)
    bin_c = Counter(q["hint_bin"] for q in queries)
    phase_c = Counter(q["phase"] for q in queries)
    tool_c = Counter(q["needs_tools"] for q in queries)
    print(f"\nmargin_check (n={n}):", flush=True)
    for b, frac in BIN_FRAC.items():
        print(f"  bin {b}: {bin_c[b]/n:.1%} (target {frac:.1%})", flush=True)
    for p, frac in PHASE_FRAC.items():
        print(f"  phase {p}: {phase_c[p]/n:.1%} (target {frac:.1%})", flush=True)
    for t, frac in TOOLS_FRAC.items():
        print(f"  tools={t}: {tool_c[t]/n:.1%} (target {frac:.1%})", flush=True)

    # Cost projection
    avg_tok = sum(q["tokens"] for q in queries) / n
    in_tok = max(500, int(avg_tok))
    cheap = (in_tok * 0.15 + 300 * 0.25) / 1e6
    esc = (in_tok * 1.00 + 300 * 2.50) / 1e6
    per_row = 0.75 * cheap + 0.25 * esc
    total_cost = n * per_row
    print(f"\nteacher_cost_projection: rows={n} avg_tokens={avg_tok:.0f} "
          f"per_row=${per_row:.6f} total=${total_cost:.2f} cap=$8.00", flush=True)

    # Write pool
    _write_jsonl(queries, POOL_OUT)
    print(f"\npool -> {POOL_OUT}", flush=True)

    # Write manifest
    manifest = _build_manifest(queries)
    MANIFEST_OUT.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_OUT.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"manifest -> {MANIFEST_OUT}", flush=True)
    for sp, ids in manifest["splits"].items():
        print(f"  {sp}: {len(ids)}", flush=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
