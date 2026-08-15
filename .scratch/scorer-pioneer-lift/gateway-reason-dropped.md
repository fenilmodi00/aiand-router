# Gateway `x-router-reason` dropped

**Decision:** Pioneer-like trained routing does **not** require restoring the gateway `x-router-reason` header. The trained contract is bin + calibrated P(success) + cheapest-above-bar, not Decision-contract reason strings.

**Revert:** `1e734c7` (reverts `26718d5`)

**Accepted out of scope:** 7 failing `tests/test_gateway.py` cases that assert `x-router-reason` remain red; not skipped/xfailed/deleted for this lift.
