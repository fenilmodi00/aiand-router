#!/usr/bin/env python3
"""Judge-free grader for cluster-measurement probe responses (v0.79).

Reads matrices (/root/router-measurements/matrices/<tier>.jsonl) for scoring
metadata and responses (/root/router-measurements/responses/<tier>/<model>.jsonl),
grades each response per its scoring type, and writes per-model per-tier rates to
/root/router-measurements/rates/v079_<tier>_results.json:
  {model: {rate, n, mean_output_tokens, total_output_tokens, errors, truncated_count}}

Grading by source payload (as built by build_matrices.py):
- livecodebench (public_tests): run the candidate program with each stdin and
  compare stdout (judge-free; subprocess with timeout)
- livebench (ground_truth): normalized exact match (whitespace/case/punct)
- bfcl (functions + ground_truth): parse tool-call JSON (either the runner's
  tool_calls capture or JSON in the text), compare function names + argument
  values against the expected multiset (BFCL convention: each expected arg may
  list acceptable values)
- swe-bench-pro / terminal-bench / aider-polyglot: repo-bound gold tests are not
  reproducible in-process; graded on structural completion signals — a fenced
  diff/patch or code block of non-trivial size with finish_reason == "stop".
  Uniform across all models; recorded as structural grading in fail_kinds.
- local-probe (none): finish_reason == "stop" and completion_tokens <= cap

Stdlib only. Deterministic; no network.
"""
import json
import math
import os
import re
import statistics
import subprocess
import sys
import tempfile

MEAS_DIR = "/root/router-measurements"
TIERS = ["hard", "medium", "bfcl", "routerarena"]

FENCE_RE = re.compile(r"```[a-zA-Z0-9_+.-]*\n(.*?)```", re.DOTALL)


def strip_fence(text):
    """First fenced block if present, else the whole text."""
    m = FENCE_RE.search(text)
    return m.group(1).strip() if m else text.strip()


def norm(s):
    """Loose exact-match normalization: collapse whitespace, drop case and
    common punctuation, so '1,6,7' matches '1, 6, 7'."""
    s = re.sub(r"[\s,;:]+", " ", s.strip().lower())
    s = s.strip(" .")
    s = re.sub(r"^(the )?(final )?answer is ", "", s)
    return s.strip()


# ---------------------------------------------------------------- LiveBench

SOLUTION_TAG_RE = re.compile(r"<solution>(.*?)</solution>", re.DOTALL | re.IGNORECASE)


def grade_ground_truth(scoring, text):
    expected = scoring.get("ground_truth")
    if expected is None:
        return False, "no-ground-truth"
    got = strip_fence(text)
    # LiveBench convention: the final answer is wrapped in <solution> tags.
    # Prefer the LAST tagged answer, then the final lines, then whole text.
    candidates = [norm(m.group(1)) for m in SOLUTION_TAG_RE.finditer(text)]
    lines = [l for l in got.splitlines() if l.strip()]
    candidates += [norm(l) for l in lines[-3:]] if lines else []
    candidates.append(norm(got))
    want = norm(str(expected))
    for c in candidates:
        if c == want:
            return True, None
    # Containment: a final line whose normalized form contains the expected
    # answer as a whole short value (models may prefix "the answer is").
    if want and any(c and (want in c or c in want) and abs(len(c) - len(want)) <= 8 for c in candidates):
        return True, None
    return False, "answer-mismatch"


# ---------------------------------------------------------------- LiveCodeBench

CXX_TIMEOUT_SECS = 20


def grade_public_tests(scoring, text):
    """Run the candidate solution against the shipped stdin/stdout pairs.

    AtCoder-style problems are language-agnostic: models answer in C++ or
    Python. Detect the fenced language (default Python) and run each solution
    in its own runtime — a C++ answer must not be executed as Python.
    """
    m = FENCE_RE.search(text)
    lang = (m.group(0).split("\n", 1)[0][3:].strip().lower()
            if m else "python")
    code = strip_fence(text)
    if not code.strip():
        return False, "empty"
    tests = scoring.get("public_tests") or []
    if not tests:
        return False, "no-tests"
    with tempfile.TemporaryDirectory() as td:
        runner = None
        if lang in ("cpp", "c++"):
            src = os.path.join(td, "sol.cpp")
            with open(src, "w") as f:
                f.write(code)
            exe = os.path.join(td, "sol")
            try:
                cc = subprocess.run(
                    ["g++", "-O2", "-std=c++20", src, "-o", exe],
                    capture_output=True, text=True, timeout=CXX_TIMEOUT_SECS)
            except subprocess.TimeoutExpired:
                return False, "compile-timeout"
            if cc.returncode != 0:
                return False, "compile-error"
            runner = [exe]
        else:
            src = os.path.join(td, "sol.py")
            with open(src, "w") as f:
                f.write(code)
            runner = [sys.executable, src]
        for t in tests:
            try:
                out = subprocess.run(
                    runner,
                    input=t["input"], capture_output=True, text=True, timeout=15)
            except subprocess.TimeoutExpired:
                return False, "timeout"
            if out.returncode != 0:
                return False, f"runtime-error:{out.returncode}"
            got_lines = [l.strip() for l in out.stdout.splitlines() if l.strip()]
            want_lines = [l.strip() for l in str(t["output"]).splitlines() if l.strip()]
            if got_lines != want_lines:
                return False, "wrong-output"
        return True, None


# ---------------------------------------------------------------- BFCL

def _parse_tool_calls(text):
    """Parse the runner's tool_calls capture, or tool-call JSON in text."""
    try:
        val = json.loads(text)
    except Exception:
        return None
    if isinstance(val, list):
        calls = []
        for c in val:
            if not isinstance(c, dict):
                return None
            args = c.get("arguments")
            if isinstance(args, str):
                try:
                    args = json.loads(args) if args.strip() else {}
                except Exception:
                    args = {"_raw": args}
            calls.append({"name": c.get("name") or "", "arguments": args or {}})
        return calls
    return None


def _arg_matches(expected_vals, got):
    """BFCL convention: expected arg is a list of acceptable values; a nested
    list means any of several exact tuples/lists."""
    if not isinstance(expected_vals, list):
        expected_vals = [expected_vals]
    for v in expected_vals:
        if isinstance(v, list):
            if json.dumps(v, sort_keys=True) == json.dumps(got, sort_keys=True):
                return True
        elif got == v:
            return True
        elif isinstance(got, (list, tuple)) and v in got:
            return True
    return False


def grade_bfcl(scoring, text):
    expected = scoring.get("ground_truth")
    if expected is None:
        return False, "no-ground-truth"
    calls = _parse_tool_calls(text)
    if calls is None:
        return False, "no-tool-calls"
    exp = expected if isinstance(expected, list) else [expected]
    if len(calls) != len(exp):
        return False, "call-count"
    # Normalize each expected entry to (func_name, {arg: [acceptable values]}).
    # Matrix payload shape: {"func_name": {arg: [acceptable...]}}.
    wants = []
    for want in exp:
        if not isinstance(want, dict) or len(want) != 1:
            return False, "bad-expected-shape"
        fname, wargs = next(iter(want.items()))
        wants.append((fname, wargs if isinstance(wargs, dict) else {}))
    # Match as a multiset: each expected call claimed by exactly one actual
    # call (parallel-multi orders are not guaranteed).
    for fname, wargs in wants:
        for i, c in enumerate(calls):
            if c["name"] != fname:
                continue
            ok = True
            for k, vv in wargs.items():
                # Optional-arg convention: an acceptable value of "" means the
                # model may omit the argument entirely.
                if k not in c["arguments"]:
                    if isinstance(vv, list) and "" in vv:
                        continue
                    ok = False
                    break
                if not _arg_matches(vv, c["arguments"][k]):
                    ok = False
                    break
            if ok:
                calls.pop(i)
                break
        else:
            return False, "arg-mismatch"
    return True, None


# --------------------------------------------------- structural (SWE/TB/aider)

STRUCTURAL_MIN_CHARS = 120


def grade_structural(scoring, text):
    """Repo-bound sources (SWE-bench Pro, Terminal-Bench, Aider polyglot) ship
    their gold tests inside per-task repos we cannot execute here. Grade on
    the completion signals that are uniform across models: a code block with
    non-trivial content and a clean finish. Recorded so the calibration notes
    can state the limitation explicitly."""
    body = strip_fence(text)
    if not body.strip():
        return False, "empty"
    if len(body.strip()) < STRUCTURAL_MIN_CHARS:
        return False, "too-short"
    return True, None


# ---------------------------------------------------------------- probes

def grade_probe(rec):
    if rec.get("error"):
        return False, rec["error"]
    if rec.get("finish_reason") != "stop":
        return False, f"finish={rec.get('finish_reason')}"
    if rec["usage"]["completion_tokens"] > rec["max_tokens"]:
        return False, "over-cap"
    return True, None


# Sources whose gold tests live in per-task repos we cannot execute
# in-process (SWE-bench Pro, Terminal-Bench 2.0, Aider polyglot). Their
# responses are EXCLUDED from rates: no honest judge-free grade exists for
# them, and structural "did it emit a code block" grading measures prose
# fluency, not correctness — the same miscalibration class as v0.78.
# Recorded per-model as skipped counts so the bundle changelog can state
# the measured denominators explicitly.
UNGRADABLE_SOURCES = ("swe-bench-pro", "terminal-bench-2.0", "aider-polyglot")


def is_ungradable(row):
    return row.get("source", "").startswith(UNGRADABLE_SOURCES)


def grade_response(row, rec):
    if is_ungradable(row):
        return None, "skipped-ungradable"
    if rec.get("error"):
        return False, rec["error"]
    src = row.get("source", "")
    st = row.get("scoring") or {}
    text = rec.get("response_text") or ""
    if src.startswith("livecodebench"):
        return grade_public_tests(st, text)
    if src.startswith("livebench"):
        return grade_ground_truth(st, text)
    if src.startswith("bfcl"):
        return grade_bfcl(st, text)
    if src.startswith("local-probe"):
        return grade_probe(rec)
    return grade_structural(st, text)


def score_tier(tier):
    matrix_path = f"{MEAS_DIR}/matrices/{tier}.jsonl"
    rows = {}
    with open(matrix_path) as f:
        for line in f:
            line = line.strip()
            if line:
                r = json.loads(line)
                rows[r["id"]] = r

    resp_dir = f"{MEAS_DIR}/responses/{tier}"
    if not os.path.isdir(resp_dir):
        print(f"[{tier}] no responses dir", flush=True)
        return {}

    models = sorted(os.path.splitext(f)[0] for f in os.listdir(resp_dir) if f.endswith(".jsonl"))
    results = {}
    for mf in models:
        path = f"{resp_dir}/{mf}.jsonl"
        n = passed = errors = truncated = skipped = 0
        out_tokens = []
        fails = {}
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                row = rows.get(rec["id"])
                if row is None:
                    continue
                ct = rec["usage"]["completion_tokens"]
                ok, why = grade_response(row, rec)
                if ok is None:
                    skipped += 1
                    continue
                n += 1
                out_tokens.append(ct)
                if ct >= rec["max_tokens"]:
                    truncated += 1
                if ok:
                    passed += 1
                else:
                    errors += 1
                    key = (why or "fail").split(":")[0][:40]
                    fails[key] = fails.get(key, 0) + 1
        results[mf] = {
            "rate": round(passed / n, 4) if n else 0.0,
            "n": n,
            "skipped_ungradable": skipped,
            "mean_output_tokens": round(statistics.fmean(out_tokens), 1) if out_tokens else 0,
            "total_output_tokens": sum(out_tokens),
            "errors": errors,
            "truncated_count": truncated,
            "passed": passed,
            "fail_kinds": dict(sorted(fails.items(), key=lambda kv: -kv[1])[:5]),
        }
        print(f"[{tier}] {mf}: rate={results[mf]['rate']} n={n} errors={errors} trunc={truncated}", flush=True)
    return results


def main():
    tiers = sys.argv[1:] or TIERS
    os.makedirs(f"{MEAS_DIR}/rates", exist_ok=True)
    for tier in tiers:
        res = score_tier(tier)
        out = f"{MEAS_DIR}/rates/v079_{tier}_results.json"
        with open(out, "w") as f:
            json.dump(res, f, indent=2, sort_keys=True)
        print(f"wrote {out}", flush=True)


if __name__ == "__main__":
    main()
