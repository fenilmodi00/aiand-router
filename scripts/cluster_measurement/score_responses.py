#!/usr/bin/env python3
"""Judge-free grader for cluster-measurement probe responses (v0.79).

Reads matrices (/root/router-measurements/matrices/<tier>.jsonl) for scoring
metadata and responses (/root/router-measurements/responses/<tier>/<model>.jsonl),
grades each response per its scoring type, and writes per-model per-tier rates to
/root/router-measurements/rates/v079_<tier>_results.json:
  {model: {rate, n, mean_output_tokens, total_output_tokens, errors, truncated_count}}

Scoring types:
- tests:    strip code fences, exec code under a sandboxed namespace, run test asserts
- exact:    normalize whitespace and compare against `expected`
- diff:     same as exact (expected final diff text) with stricter whitespace trim
- schema:   parse JSON (fences stripped) and validate required keys/types
- none:     conversational — pass iff finish_reason == "stop" and completion_tokens <= max_tokens

Stdlib only. Deterministic; no network.
"""
import json
import math
import os
import re
import statistics
import sys

MEAS_DIR = "/root/router-measurements"
TIERS = ["hard", "medium", "bfcl", "routerarena"]

FENCE_RE = re.compile(r"^```[a-zA-Z0-9_-]*\n(.*?)\n```\s*$", re.DOTALL)


def strip_fence(text):
    m = FENCE_RE.match(text.strip())
    if m:
        return m.group(1)
    # leading fence without close, or inline ```code```
    t = text.strip()
    if t.startswith("```"):
        lines = t.splitlines()
        lines = lines[1:]
        while lines and lines[-1].strip() == "```":
            lines.pop()
        return "\n".join(lines)
    return t


def norm(s):
    return re.sub(r"\s+", " ", s.strip().lower())


def grade_tests(prompt_meta, text):
    code = strip_fence(text)
    if not code.strip():
        return False, "empty"
    tests = prompt_meta.get("tests") or []
    ns = {"__name__": "__main__"}
    try:
        exec(compile(code, "<candidate>", "exec"), ns)
    except Exception as e:
        return False, f"exec-fail: {type(e).__name__}: {e}"
    for t in tests:
        # test entry: {"name"?: str, "code"?: str} — code runs with candidate namespace in scope
        tcode = t.get("code") if isinstance(t, dict) else str(t)
        if not tcode:
            continue
        try:
            exec(compile(tcode, "<test>", "exec"), dict(ns))
        except AssertionError as e:
            return False, f"assert: {e}"
        except Exception as e:
            return False, f"test-error: {type(e).__name__}: {e}"
    return True, None


def grade_exact(prompt_meta, text):
    expected = prompt_meta.get("expected") or ""
    if prompt_meta.get("strip_fence", True):
        text = strip_fence(text)
    return norm(text) == norm(expected), None


def grade_diff(prompt_meta, text):
    expected = prompt_meta.get("expected") or ""
    got = strip_fence(text).strip()
    exp = expected.strip()
    if got == exp:
        return True, None
    # tolerate line-ending and trailing-whitespace-only differences
    got_lines = [l.rstrip() for l in got.splitlines() if l.strip()]
    exp_lines = [l.rstrip() for l in exp.splitlines() if l.strip()]
    return got_lines == exp_lines, None


def check_value(schema, val):
    t = schema.get("type")
    if t == "object":
        if not isinstance(val, dict):
            return False
        for k, sub in (schema.get("properties") or {}).items():
            if k in schema.get("required", []) and k not in val:
                return False
            if k in val and not check_value(sub, val[k]):
                return False
        return True
    if t == "array":
        if not isinstance(val, list):
            return False
        return all(check_value(schema.get("items", {}), v) for v in val)
    if t == "string":
        return isinstance(val, str)
    if t == "number":
        return isinstance(val, (int, float)) and not isinstance(val, bool)
    if t == "integer":
        return isinstance(val, int) and not isinstance(val, bool)
    if t == "boolean":
        return isinstance(val, bool)
    if t == "null":
        return val is None
    return True  # unknown/absent type: accept


def extract_json(text):
    t = strip_fence(text).strip()
    try:
        return json.loads(t)
    except Exception:
        pass
    # first balanced {...} or [...] block
    for opener, closer in (("{", "}"), ("[", "]")):
        start = t.find(opener)
        if start < 0:
            continue
        depth = 0
        for i in range(start, len(t)):
            if t[i] == opener:
                depth += 1
            elif t[i] == closer:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(t[start:i + 1])
                    except Exception:
                        break
        break
    return None


def grade_schema(prompt_meta, text):
    schema = prompt_meta.get("schema") or {}
    val = extract_json(text)
    if val is None:
        return False, "no-json"
    if not check_value(schema, val):
        return False, "schema-violation"
    return True, None


def grade_none(prompt_meta, rec):
    if rec.get("error"):
        return False, rec["error"]
    if rec.get("finish_reason") != "stop":
        return False, f"finish={rec.get('finish_reason')}"
    if rec["usage"]["completion_tokens"] > rec["max_tokens"]:
        return False, "over-cap"
    return True, None


GRADERS = {
    "tests": grade_tests,
    "exact": grade_exact,
    "diff": grade_diff,
    "schema": grade_schema,
}


def grade_response(row, rec):
    st = row.get("scoring") or {}
    stype = st.get("type", "none")
    if rec.get("error"):
        return False, rec["error"]
    if stype == "none":
        return grade_none(row, rec)
    g = GRADERS.get(stype)
    if g is None:
        return False, f"unknown-scoring:{stype}"
    return g(st, rec.get("response_text") or "")


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
        n = passed = errors = truncated = 0
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
                n += 1
                ct = rec["usage"]["completion_tokens"]
                out_tokens.append(ct)
                if ct >= rec["max_tokens"]:
                    truncated += 1
                ok, why = grade_response(row, rec)
                if ok:
                    passed += 1
                else:
                    errors += 1
                    key = (why or "fail").split(":")[0][:40]
                    fails[key] = fails.get(key, 0) + 1
        results[mf] = {
            "rate": round(passed / n, 4) if n else 0.0,
            "n": n,
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
