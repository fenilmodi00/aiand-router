//go:build smoke

package smoke

import "testing"

// TestCaching exercises the Anthropic prompt-cache path — the surface the router's
// cache-breakpoint injection broke. Asserts observable outcomes of a correct implementation.
func TestCaching(t *testing.T) {
	// Router injects a breakpoint on the large stable prefix; first call warms (or reads
	// if already warm — Anthropic TTL is ~5min), second same-prefix call must read.
	t.Run("router-injected caching warms then reads", func(t *testing.T) {
		uid := "smoke-cache-injected"
		warm := call(t, newRequest(uid).tokens(32).text("Say: one").build(t))
		requireOKMessage(t, warm)
		if warm.message.Usage.CacheCreationInputTokens <= 0 && warm.message.Usage.CacheReadInputTokens <= 0 {
			t.Errorf("first call: want cache_creation_input_tokens > 0 (cold) or cache_read_input_tokens > 0 "+
				"(already warm from a recent prior run — Anthropic's cache TTL is ~5min), got creation=%d read=%d "+
				"(router injection not engaging?)",
				warm.message.Usage.CacheCreationInputTokens, warm.message.Usage.CacheReadInputTokens)
		}

		// Same session + identical large prefix, different trailing user text.
		read := call(t, newRequest(uid).tokens(32).text("Say: two").build(t))
		requireOKMessage(t, read)
		if read.message.Usage.CacheReadInputTokens <= 0 {
			t.Errorf("second call: want cache_read_input_tokens > 0, got %d (prefix not cached/read)",
				read.message.Usage.CacheReadInputTokens)
		}
	})

	// Client at Anthropic's 4-breakpoint cap — router must not inject a 5th (pre-#821 it did).
	t.Run("client at capacity does not over-inject", func(t *testing.T) {
		// 2 extra cached tools + toolCache on the Edit tool + sysCache = 4 total
		// explicit breakpoints, exactly at capacity.
		body := newRequest("smoke-cache-capacity").tokens(32).
			cachedTools(2).toolCache("5m").sysCache("5m").
			text("Say: ok").build(t)
		r := call(t, body)
		requireOKMessage(t, r)
	})

	// Client pins ttl=1h on the final message block. The router must not inject
	// an earlier 5m breakpoint that would violate Anthropic's TTL-ordering rule.
	t.Run("ttl=1h message breakpoint is not poisoned", func(t *testing.T) {
		uid := "smoke-cache-ttl-order"
		warm := call(t, newRequest(uid).tokens(32).msgCache("1h").text("Say: alpha").build(t))
		requireOKMessage(t, warm)
		// A 1h breakpoint on the trailing block caches the whole prefix; a
		// same-prefix follow-up should read it back.
		read := call(t, newRequest(uid).tokens(32).msgCache("1h").text("Say: beta").build(t))
		requireOKMessage(t, read)
		if read.message.Usage.CacheReadInputTokens <= 0 {
			t.Errorf("ttl=1h follow-up: want cache_read_input_tokens > 0, got %d", read.message.Usage.CacheReadInputTokens)
		}
	})

	// Five explicit breakpoints exceed Anthropic's 4-cap; that rejection only
	// fires on a native Anthropic upstream. This deploy is aiand OpenAI-compat
	// only (compose MITM + host), so the turn never hits
	// translate.ErrAnthropicCacheControlOverflow.
	t.Run("overflow rejected cleanly by router", func(t *testing.T) {
		t.Skip("aiand OpenAI-compat upstream: Anthropic 4-breakpoint overflow is N/A")
	})
}
