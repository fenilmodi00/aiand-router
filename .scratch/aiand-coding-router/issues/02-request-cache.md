# 02 — Request cache

**What to build:** The same immutable request is not billed twice. A second identical call (same prompt, model, system prompt, tool schema, temperature, max tokens) is served from cache, spend does not increase, and the log shows a hit. Rehearsals and the later eval matrix become cheap.

**Blocked by:** 01 — Provider seam and gateway contract

**Status:** resolved

- [x] Cache key is the hash of prompt + model id + system prompt + tool schema + temperature + max tokens
- [x] A second identical non-stream call returns the cached body and does not invoke the upstream
- [x] Spend does not increase on a cache hit
- [x] JSONL records that the response was a cache hit
- [x] A change to any key field misses the cache and calls the upstream once
