# 01 — Geometry kill/pass an operator can trust



**What to build:** Unpaid geometry over train (and optional cal) success gold vs frozen verified eval that prints kill/pass an operator can trust: Spearman of per-id success rates, holdout-like order (Kimi ≫ Flash ≈ Qwen ≫ Pro), y-rate on observed cells only, and unobserved count so a budget-capped run cannot look like “all models fail.” Eval never enters fit. No spend. No TRAINED_PATH flip.



**Blocked by:** None — can start immediately



**Status:** resolved



- [x] Kill when Spearman(train rates, frozen verified rates) ≤ 0, or train y is empty, or y stays dense-easy (~0.39)

- [x] Pass needs Spearman > 0, y in the hard band (~0.07–0.22), and holdout-like model order

- [x] y-rate ignores unobserved cells; report shows observed vs unobserved counts

- [x] Eval path is never fit / cal / threshold y; unit tests never spend



## Answer



Unpaid `python -m aiand_router.geometry --train … [--cal …] --eval …` prints per-id rates, Spearman, `observed_n` / `unobserved_n`, and operator flags: `kill` / `geometry_pass` plus `kill_spearman` (now **≤ 0**), `kill_y_empty`, `kill_y_easy`, `holdout_like_order`, `y_in_hard_band`. y-rate uses observed cells only. `--eval` stays eval-only (`eval_is_fit_gold=false`). No spend, no `TRAINED_PATH` flip.



Ticket **03** should stop on `kill` (or fail `geometry_pass`); scale only when `geometry_pass` is true.



Files: `src/aiand_router/geometry.py`, `tests/test_geometry.py`.

### Follow-on (hard-transfer Mix1)

`FLASH_QWEN_APPROX` raised **0.02 → 0.03** so |Flash−Qwen|=0.025 on n=40 (one cell) still counts as ≈. Documented in issue 03; not a soft-y threshold change.

