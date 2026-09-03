package proxy

import (
	"context"
	"errors"
	"fmt"
	"net/http"
	"strings"
	"testing"

	"aiand/router/internal/router"
	"aiand/router/internal/router/handover"
	"aiand/router/internal/router/policy"
	"aiand/router/internal/router/sessionpin"
	"aiand/router/internal/router/turntype"
	"aiand/router/internal/translate"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

type fakeCompactionSummarizer struct {
	summary   string
	usage     handover.Usage
	err       error
	calls     int
	lastModel string
}

func (f *fakeCompactionSummarizer) SummarizeForCompaction(_ context.Context, _ *translate.RequestEnvelope, model string, _ int) (string, handover.Usage, error) {
	f.calls++
	f.lastModel = model
	return f.summary, f.usage, f.err
}

func (f *fakeCompactionSummarizer) Provider() string { return "aiand" }

// alternatingAnthropicBody builds an Anthropic body of nMsgs user/assistant
// messages (starting with user), each padded to ~perMsgPad content bytes.
func alternatingAnthropicBody(nMsgs, perMsgPad int) []byte {
	pad := strings.Repeat("x", perMsgPad)
	var sb strings.Builder
	sb.WriteString(`{"model":"moonshotai/kimi-k3","system":"sys","messages":[`)
	for i := range nMsgs {
		if i > 0 {
			sb.WriteString(",")
		}
		role := "user"
		if i%2 == 1 {
			role = "assistant"
		}
		sb.WriteString(`{"role":"` + role + `","content":"` + pad + `"}`)
	}
	sb.WriteString(`]}`)
	return []byte(sb.String())
}

// toolHeavyAnthropicBody builds nPairs of (assistant tool_use, user tool_result)
// with each tool_result carrying contentBytes of payload.
func toolHeavyAnthropicBody(nPairs, contentBytes int) []byte {
	pad := strings.Repeat("y", contentBytes)
	var sb strings.Builder
	sb.WriteString(`{"model":"moonshotai/kimi-k3","messages":[`)
	for i := range nPairs {
		if i > 0 {
			sb.WriteString(",")
		}
		id := fmt.Sprintf("t%d", i)
		sb.WriteString(`{"role":"assistant","content":[{"type":"tool_use","id":"` + id + `","name":"read","input":{}}]},`)
		sb.WriteString(`{"role":"user","content":[{"type":"tool_result","tool_use_id":"` + id + `","content":"` + pad + `"}]}`)
	}
	sb.WriteString(`]}`)
	return []byte(sb.String())
}

func TestMaybeCompact_UnderThresholdIsNoop(t *testing.T) {
	s := &Service{compactionTriggerPct: DefaultCompactionTriggerPct, compactionSummarizer: &fakeCompactionSummarizer{}}
	env, err := translate.ParseAnthropic(alternatingAnthropicBody(2, 20))
	require.NoError(t, err)
	before := env.ContextOverflowTokenEstimate()

	res, err := s.maybeCompact(context.Background(), env, compactionInput{TurnType: turntype.MainLoop, OutputReserve: 0, MaxWindow: 1_000_000, Headers: http.Header{}})
	require.NoError(t, err)
	assert.False(t, res.Applied, "a small request must not be compacted")
	assert.Equal(t, before, env.ContextOverflowTokenEstimate(), "env must be untouched below threshold")
}

func TestMaybeCompact_DisabledWhenPctZero(t *testing.T) {
	s := &Service{} // compactionTriggerPct == 0 disables the cascade
	env, err := translate.ParseAnthropic(alternatingAnthropicBody(20, 200))
	require.NoError(t, err)
	res, err := s.maybeCompact(context.Background(), env, compactionInput{TurnType: turntype.MainLoop, OutputReserve: 0, MaxWindow: 500, Headers: http.Header{}})
	require.NoError(t, err)
	assert.False(t, res.Applied)
}

func TestMaybeCompact_Tier1ClearsToolResults(t *testing.T) {
	s := &Service{compactionTriggerPct: DefaultCompactionTriggerPct} // nil summarizer
	env, err := translate.ParseAnthropic(toolHeavyAnthropicBody(20, 300))
	require.NoError(t, err)
	before := env.ContextOverflowTokenEstimate()
	// maxWindow between post-Tier-1 and pre-Tier-1 estimates so Tier-1 alone fits.
	maxWindow := before * 3 / 4

	res, err := s.maybeCompact(context.Background(), env, compactionInput{TurnType: turntype.MainLoop, OutputReserve: 0, MaxWindow: maxWindow, Headers: http.Header{}})
	require.NoError(t, err)
	assert.True(t, res.Applied)
	assert.Positive(t, res.ToolResultsCleared, "old tool results should be cleared")
	assert.False(t, res.Summarized, "nil summarizer must not summarize")
	assert.LessOrEqual(t, env.ContextOverflowTokenEstimate(), maxWindow, "must fit after Tier-1")
}

func TestMaybeCompact_Tier3Summarizes(t *testing.T) {
	fake := &fakeCompactionSummarizer{summary: "SHORT STRUCTURED SUMMARY"}
	s := &Service{compactionTriggerPct: DefaultCompactionTriggerPct, compactionSummarizer: fake}
	env, err := translate.ParseAnthropic(alternatingAnthropicBody(20, 200))
	require.NoError(t, err)

	// Window that Tier-1 (no tool results here) can't satisfy but a
	// summarize + recent-12 rewrite can.
	res, err := s.maybeCompact(context.Background(), env, compactionInput{TurnType: turntype.MainLoop, OutputReserve: 0, MaxWindow: 900, Headers: http.Header{}})
	require.NoError(t, err)
	assert.True(t, res.Applied)
	assert.True(t, res.Summarized)
	assert.Equal(t, DefaultCompactionModel, res.SummaryModel, "no warm pin → mid-tier default")
	assert.Equal(t, 1, fake.calls)
	assert.Equal(t, DefaultCompactionModel, fake.lastModel)
}

func TestMaybeCompact_ExceedsFloorReturnsSentinel(t *testing.T) {
	s := &Service{compactionTriggerPct: DefaultCompactionTriggerPct} // nil summarizer
	env, err := translate.ParseAnthropic(alternatingAnthropicBody(4, 400))
	require.NoError(t, err)

	// A window so small that even trimming to a single (large) message overflows.
	_, err = s.maybeCompact(context.Background(), env, compactionInput{TurnType: turntype.MainLoop, OutputReserve: 0, MaxWindow: 30, Headers: http.Header{}})
	require.Error(t, err)
	assert.True(t, errors.Is(err, ErrContextWindowExceeded))
}

func TestMaybeCompact_SkipsHardPinnedTurns(t *testing.T) {
	fake := &fakeCompactionSummarizer{summary: "x"}
	s := &Service{compactionTriggerPct: DefaultCompactionTriggerPct, compactionSummarizer: fake}
	env, err := translate.ParseAnthropic(alternatingAnthropicBody(20, 200))
	require.NoError(t, err)
	before := env.ContextOverflowTokenEstimate()

	// A Compaction turn is the client's own compaction request — the router
	// must not rewrite it, even when it's over threshold.
	res, err := s.maybeCompact(context.Background(), env, compactionInput{TurnType: turntype.Compaction, OutputReserve: 0, MaxWindow: 900, Headers: http.Header{}})
	require.NoError(t, err)
	assert.False(t, res.Applied, "hard-pinned turns must skip compaction")
	assert.Equal(t, 0, fake.calls, "summarizer must not be called for a Compaction turn")
	assert.Equal(t, before, env.ContextOverflowTokenEstimate(), "env must be untouched")
}

func TestMaybeCompact_AuthoritativePolicyNeverCallsSummarizer(t *testing.T) {
	strategy := router.Strategy("authoritative-compaction-test")
	fake := &fakeCompactionSummarizer{summary: "must not run"}
	s := (&Service{
		compactionTriggerPct: DefaultCompactionTriggerPct,
		compactionSummarizer: fake,
	}).WithPolicyStrategy(policy.StrategySpec{
		Strategy: strategy,
		Router:   &authoritativeTestRouter{},
		Capabilities: policy.Capabilities{
			AuthoritativePerTurnSelection: true,
		},
	})
	env, err := translate.ParseAnthropic(alternatingAnthropicBody(20, 200))
	require.NoError(t, err)
	ctx := router.WithStrategy(context.Background(), strategy)

	result, _ := s.maybeCompact(ctx, env, compactionInput{TurnType: turntype.MainLoop, OutputReserve: 100, MaxWindow: 700, Headers: http.Header{}})

	assert.Equal(t, 0, fake.calls)
	assert.False(t, result.Summarized)
	assert.Positive(t, result.TrimmedToRecent, "authoritative routing must still rescue-trim when cleanup does not fit")
}

func TestWithCompaction_ZeroPctDisables(t *testing.T) {
	// ROUTER_COMPACTION_PCT=0 must disable, not fall back to the default.
	s := (&Service{}).WithCompaction(nil, 0)
	assert.Equal(t, 0.0, s.compactionTriggerPct)
	// A negative/out-of-range value falls back to the default.
	s = (&Service{}).WithCompaction(nil, -1)
	assert.Equal(t, DefaultCompactionTriggerPct, s.compactionTriggerPct)
	s = (&Service{}).WithCompaction(nil, 2)
	assert.Equal(t, DefaultCompactionTriggerPct, s.compactionTriggerPct)
}

func TestSelectCompactionSummarizer_WindowAware(t *testing.T) {
	s := &Service{}
	assert.Equal(t, DefaultCompactionModel, s.selectCompactionSummarizer(1_000, ""), "small history → mid-tier default")
	assert.Equal(t, largeWindowSummarizerModel, s.selectCompactionSummarizer(300_000, ""), "history over the default's window → large-window model")
	assert.Equal(t, "", s.selectCompactionSummarizer(5_000_000, ""), "history over every window → none")

	assert.Equal(t, "moonshotai/kimi-k2.7", s.selectCompactionSummarizer(1_000, "moonshotai/kimi-k2.7"), "warm pin summarizes its own session")
	assert.Equal(t, DefaultCompactionModel, s.selectCompactionSummarizer(1_000, "deepseek-ai/deepseek-v4-flash"), "low-tier pin is not reused as summarizer")
	assert.Equal(t, DefaultCompactionModel, s.selectCompactionSummarizer(1_000, "totally-unknown-model"), "non-catalog pin is not reused as summarizer")
	assert.Equal(t, largeWindowSummarizerModel, s.selectCompactionSummarizer(300_000, "moonshotai/kimi-k2.7"), "pin that can't ingest the history is skipped")

	custom := &Service{compactionModel: "zai-org/glm-5.3"}
	assert.Equal(t, "zai-org/glm-5.3", custom.selectCompactionSummarizer(1_000, ""), "ROUTER_COMPACTION_MODEL overrides the default")
}

func TestCompactionPolicyFor(t *testing.T) {
	assert.True(t, compactionPolicyFor(ClientAppClaudeCode).DeferToClient, "Claude Code auto-compacts itself")
	assert.Equal(t, claudeCodeAutoCompactBuffer, compactionPolicyFor(ClientAppClaudeCode).ClientBuffer)
	assert.False(t, compactionPolicyFor(ClientAppCodex).DeferToClient, "Codex gets the router cascade")
	assert.Equal(t, defaultCompactionPolicy, compactionPolicyFor(""), "unknown client → default policy")
	assert.Equal(t, defaultCompactionPolicy, compactionPolicyFor("some-new-harness"))
}

func TestClientWouldCompact(t *testing.T) {
	cc := compactionPolicyFor(ClientAppClaudeCode)
	// Pool serves the window the client sizes against: the client's own
	// auto-compact (at window-13K) fires before the router needs to.
	assert.True(t, clientWouldCompact(cc, "moonshotai/kimi-k3", 1_048_576))
	// Pool's largest window is below the client's compaction point: router
	// must compact or the request dead-ends.
	assert.False(t, clientWouldCompact(cc, "moonshotai/kimi-k3", 262_144))
	assert.False(t, clientWouldCompact(compactionPolicyFor(ClientAppCodex), "zai-org/glm-5.3", 1_048_576), "non-deferring harness never defers")
	assert.False(t, clientWouldCompact(cc, "", 1_048_576), "unknown requested model → no deferral")
}

func TestMaybeCompact_ClaudeCodeDefersWhenPoolServesClientWindow(t *testing.T) {
	fake := &fakeCompactionSummarizer{summary: "x"}
	// Tiny trigger so a small fixture is "over threshold" against a large pool
	// that matches the requested model's window.
	s := &Service{compactionTriggerPct: 0.001, compactionSummarizer: fake}
	env, err := translate.ParseAnthropic(toolHeavyAnthropicBody(20, 300))
	require.NoError(t, err)
	before := env.ContextOverflowTokenEstimate()

	res, err := s.maybeCompact(context.Background(), env, compactionInput{
		TurnType: turntype.MainLoop, MaxWindow: 1_048_576, RequestedModel: "moonshotai/kimi-k3", ClientApp: ClientAppClaudeCode, Headers: http.Header{},
	})
	require.NoError(t, err)
	assert.True(t, res.DeferredToClient, "Claude Code compacts itself at window-13K; pool serves that window")
	assert.False(t, res.Applied)
	assert.Equal(t, before, env.ContextOverflowTokenEstimate(), "env must be untouched when deferred")

	// Same shape from Codex: the router owns compaction.
	env2, err := translate.ParseAnthropic(toolHeavyAnthropicBody(20, 300))
	require.NoError(t, err)
	res, err = s.maybeCompact(context.Background(), env2, compactionInput{
		TurnType: turntype.MainLoop, MaxWindow: 1_048_576, RequestedModel: "zai-org/glm-5.3", ClientApp: ClientAppCodex, Headers: http.Header{},
	})
	require.NoError(t, err)
	assert.False(t, res.DeferredToClient)
	assert.True(t, res.Applied, "Codex gets Tier-1 tool-result cleanup")
	assert.Positive(t, res.ToolResultsCleared)

	// Claude Code against a pool smaller than its believed window: the
	// client's own compaction would fire too late, so the router compacts.
	env3, err := translate.ParseAnthropic(toolHeavyAnthropicBody(20, 300))
	require.NoError(t, err)
	res, err = s.maybeCompact(context.Background(), env3, compactionInput{
		TurnType: turntype.MainLoop, MaxWindow: 262_144, RequestedModel: "moonshotai/kimi-k3", ClientApp: ClientAppClaudeCode, Headers: http.Header{},
	})
	require.NoError(t, err)
	assert.False(t, res.DeferredToClient)
	assert.True(t, res.Applied)
}

func TestMaybeCompact_OverflowNeverDefers(t *testing.T) {
	// Even a deferring harness must be compacted when the request already
	// overflows the pool: the client can't help on this turn.
	s := &Service{compactionTriggerPct: DefaultCompactionTriggerPct}
	env, err := translate.ParseAnthropic(toolHeavyAnthropicBody(20, 300))
	require.NoError(t, err)
	before := env.ContextOverflowTokenEstimate()
	res, err := s.maybeCompact(context.Background(), env, compactionInput{
		TurnType: turntype.MainLoop, MaxWindow: before * 3 / 4, RequestedModel: "moonshotai/kimi-k3", ClientApp: ClientAppClaudeCode, Headers: http.Header{},
	})
	require.NoError(t, err)
	assert.False(t, res.DeferredToClient)
	assert.Positive(t, res.ToolResultsCleared)
}

func TestCompactionHardPin(t *testing.T) {
	s := &Service{compactionHardPinEnabled: true}
	var key [sessionpin.SessionKeyLen]byte
	ctx := context.Background()

	p, m, ok := s.compactionHardPin(ctx, key, "", router.Request{})
	require.True(t, ok)
	assert.Equal(t, "aiand", p)
	assert.Equal(t, DefaultCompactionModel, m, "no pin → mid-tier default")

	_, _, ok = s.compactionHardPin(ctx, key, "", router.Request{EnabledProviders: map[string]struct{}{"not-aiand": {}}})
	assert.False(t, ok, "aiand disabled for the tenant → fall back to generic hard-pin")

	_, _, ok = s.compactionHardPin(ctx, key, "", router.Request{ExcludedModels: map[string]struct{}{DefaultCompactionModel: {}}})
	assert.False(t, ok, "excluded default with no pin → fall back to generic hard-pin")

	unavailable := &Service{compactionHardPinEnabled: true, availableModels: map[string]struct{}{"deepseek-ai/deepseek-v4-flash": {}}}
	_, _, ok = unavailable.compactionHardPin(ctx, key, "", router.Request{})
	assert.False(t, ok, "default not routable in this deployment → fall back to generic hard-pin")
}

func TestMaxEligibleContextWindow(t *testing.T) {
	s := &Service{availableModels: map[string]struct{}{"deepseek-ai/deepseek-v4-flash": {}}}
	assert.Equal(t, 1_048_576, s.maxEligibleContextWindow(nil, nil, 0))
	assert.Equal(t, 1_048_576+5_000, s.maxEligibleContextWindow(nil, nil, 5_000), "aiand flash strips Anthropic signatures, so sig savings expand the window")
	assert.Equal(t, 0, s.maxEligibleContextWindow(map[string]struct{}{"deepseek-ai/deepseek-v4-flash": {}}, nil, 0), "policy-excluding the only model leaves no window")

	sStrip := &Service{availableModels: map[string]struct{}{"qwen/qwen3.8-27b": {}}}
	assert.Equal(t, 262_144, sStrip.maxEligibleContextWindow(nil, nil, 0))
	assert.Equal(t, 262_144+5_000, sStrip.maxEligibleContextWindow(nil, nil, 5_000), "stripping model gains signature savings as headroom")
}

func TestClassifyDispatchError_ContextWindowExceeded(t *testing.T) {
	cls, ok := ClassifyDispatchError(fmt.Errorf("wrapped: %w", ErrContextWindowExceeded))
	require.True(t, ok)
	assert.Equal(t, http.StatusRequestEntityTooLarge, cls.Status)
	assert.Equal(t, DispatchErrorContextWindowExceeded, cls.Kind)
	assert.True(t, cls.Kind.IsClientError())
}

func TestMaybeCompact_Tier3RunsAboveTriggerEvenWhenFitting(t *testing.T) {
	// A history over the trigger but still under the window must be
	// summarized now — waiting until it overflows means no summarizer can
	// ingest it any more (Tier-3 was unreachable against a 1M pool).
	fake := &fakeCompactionSummarizer{summary: "SUMMARY"}
	s := &Service{compactionTriggerPct: DefaultCompactionTriggerPct, compactionSummarizer: fake}
	env, err := translate.ParseAnthropic(alternatingAnthropicBody(20, 200))
	require.NoError(t, err)
	before := env.ContextOverflowTokenEstimate()

	res, err := s.maybeCompact(context.Background(), env, compactionInput{
		TurnType: turntype.MainLoop, MaxWindow: before + before/10, ClientApp: ClientAppCodex, Headers: http.Header{},
	})
	require.NoError(t, err)
	assert.True(t, res.Summarized, "over trigger, under window → summarize")
	assert.Equal(t, 1, fake.calls)
	assert.Zero(t, res.TrimmedToRecent, "fitting request must not be rescue-trimmed")
}

func TestMaybeCompact_Tier3RevertsWhenSummaryRewriteOverflows(t *testing.T) {
	// A fitting request whose tail is nearly the whole window: prepending a
	// summary would push it over, so the rewrite is discarded instead of
	// falling through to rescue trimming.
	fake := &fakeCompactionSummarizer{summary: strings.Repeat("SUMMARY ", 2_000)}
	s := &Service{compactionTriggerPct: DefaultCompactionTriggerPct, compactionSummarizer: fake}
	env, err := translate.ParseAnthropic(alternatingAnthropicBody(4, 400))
	require.NoError(t, err)
	before := env.ContextOverflowTokenEstimate()

	res, err := s.maybeCompact(context.Background(), env, compactionInput{
		TurnType: turntype.MainLoop, MaxWindow: before + 10, ClientApp: ClientAppCodex, Headers: http.Header{},
	})
	require.NoError(t, err)
	assert.Equal(t, 1, fake.calls)
	assert.False(t, res.Summarized)
	assert.Zero(t, res.TrimmedToRecent)
	assert.Equal(t, DefaultCompactionModel, res.SummaryModel, "summary call is still billed")
	assert.Equal(t, before, env.ContextOverflowTokenEstimate(), "history restored")
}
