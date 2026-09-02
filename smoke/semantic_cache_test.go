//go:build smoke

package smoke

import (
	"fmt"
	"net/http"
	"testing"
	"time"
)

// TestSemanticCache verifies the cross-request semantic response cache on a
// live router: an identical non-streaming turn stores on miss (no x-router-cache
// header) and replays on repeat (x-router-cache: hit). Streaming is asserted to
// bypass the cache entirely.
func TestSemanticCache(t *testing.T) {
	t.Run("identical non-stream turn hits semantic cache on repeat", func(t *testing.T) {
		// Unique per-run session id: a fixed one would hit a cache entry stored
		// by a previous run of this same test (shared key + shared prompt),
		// turning the expected cold miss into a hit.
		runID := fmt.Sprintf("smoke-semantic-cache-%d", time.Now().UnixNano())
		body := newRequest(runID).tokens(1024).
			text("Reply with exactly the word: parity. Do not use tools.").
			build(t)

		// Use auto routing: model-pinned (forced) turns short-circuit the turn
		// loop before the scorer, carry no routing metadata (no embedding or
		// cluster ids), and therefore structurally bypass the semantic cache.
		// Auto routing goes through the scorer and exercises the real
		// store+hit path.
		miss := callModel(t, body, "auto")
		requireOKMessage(t, miss)
		if got := miss.headers.Get(headerRouterCache); got != "" {
			t.Errorf("first call: want no %s header (cache miss), got %q", headerRouterCache, got)
		}

		hit := callModel(t, body, "auto")
		requireOKMessage(t, hit)
		if got := hit.headers.Get(headerRouterCache); got != routerCacheHit {
			t.Errorf("second call: want %s=%q (cache hit), got %q", headerRouterCache, routerCacheHit, got)
		}
	})

	t.Run("streaming bypasses semantic cache", func(t *testing.T) {
		// Auto routing: pinned turns never reach the semantic cache, and a
		// per-run id keeps this subtest cold across suite reruns.
		streamID := fmt.Sprintf("smoke-semantic-cache-stream-%d", time.Now().UnixNano())
		body := newRequest(streamID).tokens(1024).streaming().
			text("Reply with exactly the word: stream. Do not use tools.").
			build(t)

		first := callModel(t, body, "auto")
		if first.status != http.StatusOK {
			t.Fatalf("stream first: want 200, got %d; body: %s", first.status, truncate(first.body, 400))
		}
		if got := first.headers.Get(headerRouterCache); got != "" {
			t.Errorf("streaming first call: want no %s header, got %q", headerRouterCache, got)
		}

		second := callModel(t, body, "auto")
		if second.status != http.StatusOK {
			t.Fatalf("stream second: want 200, got %d; body: %s", second.status, truncate(second.body, 400))
		}
		if got := second.headers.Get(headerRouterCache); got != "" {
			t.Errorf("streaming repeat: want no %s header (streaming never cached), got %q", headerRouterCache, got)
		}
	})
}
