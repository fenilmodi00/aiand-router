//go:build smoke

package smoke

import (
	"net/http"
	"testing"
)

// TestMultiturn replays assistant-role conversation history — the traffic
// shape that 400s if the chat→Responses translator emits output_text parts
// outside fully-typed message items (launch blocker #01). Both turns pin the
// suite model so the decision stays deterministic.
func TestMultiturn(t *testing.T) {
	const remember = "Remember the word banana"
	const recall = "What word did I ask you to remember?"

	t.Run("non-stream two-turn conversation", func(t *testing.T) {
		body := newRequest("smoke-multiturn-nonstream").tokens(64).
			history("user", remember).
			history("assistant", "Banana.").
			text(recall).build(t)
		r := call(t, body)
		requireOKMessage(t, r)
		assertServedByPin(t, r)
	})

	t.Run("stream two-turn conversation", func(t *testing.T) {
		body := newRequest("smoke-multiturn-stream").tokens(64).streaming().
			history("user", remember).
			history("assistant", "Banana.").
			text(recall).build(t)
		r := call(t, body)
		if r.status != http.StatusOK {
			t.Fatalf("stream: want 200, got %d; body: %s", r.status, truncate(r.body, 400))
		}
		assertStreamWellFormed(t, r)
		assertServedByPin(t, r)
	})
}
