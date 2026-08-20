"""QA for src/aiand_router/monitor.py — Multi-SWE-RL non-Python share monitor.

Assert-first; exits non-zero on first failure. Run:
    .venv\\Scripts\\python.exe scripts/check_monitor.py
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from aiand_router.monitor import evaluate, guess_languages, hop_is_python


def _py_row() -> dict:
    return {"payload": {"messages": [{"content": "edit src/main.py"}]}}


def _ts_row() -> dict:
    return {"payload": {"messages": [{"content": "fix src/app.ts"}]}}


def _unknown_row() -> dict:
    return {"phase": "plan", "selected": "deepseek-ai/deepseek-v4-flash"}


def _mixed_row() -> dict:
    return {"payload": {"messages": [{"content": "edit src/main.py and src/app.ts"}]}}


def _malformed_row() -> dict:
    return {}


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "status.json"

        # (a) 25% non-Python mix trips recommend_ingest.
        rows_25 = [_py_row()] * 3 + [_ts_row()]
        status = evaluate(rows_25, out_path=str(out))
        assert status["recommend_ingest"] is True, status
        assert status["share"] == 0.25, status
        assert status["n_determinable"] == 4, status
        print("PASS (a) 25% non-Python mix -> recommend_ingest true")

        # (b) 10% non-Python -> false.
        rows_10 = [_py_row()] * 9 + [_ts_row()]
        status = evaluate(rows_10, out_path=str(out))
        assert status["recommend_ingest"] is False, status
        assert status["share"] == 0.10, status
        print("PASS (b) 10% non-Python -> recommend_ingest false")

        # (c) all-unknown rows -> n_determinable 0, no crash.
        status = evaluate([_unknown_row()] * 5, out_path=str(out))
        assert status["n_determinable"] == 0, status
        assert status["share"] == 0.0, status
        print("PASS (c) all-unknown rows -> n_determinable 0, no crash")

        # (d) mixed row with .py + .ts counts as Python.
        assert "python" in guess_languages(_mixed_row())
        assert hop_is_python(_mixed_row()) is True
        print("PASS (d) mixed .py + .ts row -> Python")

        # (e) evaluate twice -> identical status file bytes (stale_state).
        evaluate(rows_25, out_path=str(out))
        first = out.read_bytes()
        evaluate(rows_25, out_path=str(out))
        second = out.read_bytes()
        assert first == second, "status file changed between identical evaluate calls"
        print("PASS (e) evaluate twice -> identical status file bytes")

        # (f) rows missing all fields -> unknown, no crash (malformed_input).
        assert guess_languages(_malformed_row()) == {"unknown"}
        assert hop_is_python(_malformed_row()) is None
        status = evaluate([_malformed_row(), None, 42], out_path=str(out))
        assert status["n_determinable"] == 0, status
        print("PASS (f) malformed rows -> unknown, no crash")

    print("ALL PASS")


if __name__ == "__main__":
    main()
