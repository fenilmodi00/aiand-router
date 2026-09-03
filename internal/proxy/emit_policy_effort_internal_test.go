package proxy

import (
	"testing"

	"github.com/stretchr/testify/assert"

	"aiand/router/internal/router/catalog"
	"aiand/router/internal/router/turntype"
	"aiand/router/internal/translate"
)

func TestApplyPolicyEffortToEmit_WiresResolvedEffortToBothFields(t *testing.T) {
	opts := translate.EmitOptions{Capabilities: catalog.CapabilitiesFor("zai-org/glm-5.3")}

	applyPolicyEffortToEmit(&opts, "low")

	assert.Equal(t, "low", opts.ForceEffort)
	assert.Equal(t, opts.ForceEffort, opts.ForceReasoningEffort,
		"policy effort must reach both emit fields")
}

func TestApplyPolicyEffortToEmit_NoOpWhenEmpty(t *testing.T) {
	opts := translate.EmitOptions{Capabilities: catalog.CapabilitiesFor("zai-org/glm-5.3")}

	applyPolicyEffortToEmit(&opts, "")

	assert.Empty(t, opts.ForceEffort)
	assert.Empty(t, opts.ForceReasoningEffort)
}

func TestApplyPolicyEffortToEmit_CapsUnsupportedLevels(t *testing.T) {
	opts := translate.EmitOptions{Capabilities: catalog.CapabilitiesFor("zai-org/glm-5.3")}

	applyPolicyEffortToEmit(&opts, "high")

	assert.Equal(t, "max", opts.ForceEffort,
		"high is not served by glm-5.3, so it must cap to the nearest level (max) before emit")
	assert.Equal(t, "max", opts.ForceReasoningEffort)
}

func TestEasyTierMinimalEffort(t *testing.T) {
	const flash = "deepseek-ai/deepseek-v4-flash"
	const scored = "cluster:v0.78 top_p=[2,4] model=" + flash + " provider=aiand"
	tests := []struct {
		name    string
		model   string
		turn    turntype.TurnType
		hardPin bool
		reason  string
		want    bool
	}{
		{name: "easy tier main loop", model: flash, turn: turntype.MainLoop, reason: scored, want: true},
		{name: "easy tier qwen main loop", model: "qwen/qwen3.8-27b", turn: turntype.MainLoop, reason: scored, want: true},
		{name: "hard tier main loop untouched", model: "moonshotai/kimi-k3", turn: turntype.MainLoop, reason: scored, want: false},
		{name: "mid tier main loop untouched", model: "motif-technologies/motif-3", turn: turntype.MainLoop, reason: scored, want: false},
		{name: "easy tier tool result untouched", model: flash, turn: turntype.ToolResult, reason: scored, want: false},
		{name: "easy tier sub-agent dispatch untouched", model: "qwen/qwen3.8-27b", turn: turntype.SubAgentDispatch, reason: scored, want: false},
		{name: "unknown model untouched", model: "definitely-not-a-model", turn: turntype.MainLoop, reason: scored, want: false},
		{name: "hard pin goes through the hard-pin branch", model: flash, turn: turntype.Classifier, hardPin: true, reason: scored, want: false},
		{name: "user-forced flash pin keeps user effort", model: flash, turn: turntype.MainLoop, reason: translate.ReasonUserForceModel, want: false},
		{name: "tier-clamped forced pin keeps user effort", model: "qwen/qwen3.8-27b", turn: turntype.MainLoop, reason: translate.ReasonUserForceModel + "+tier_clamp", want: false},
		{name: "loop escalation pin keeps its own effort", model: flash, turn: turntype.MainLoop, reason: translate.ReasonLoopEscalation, want: false},
		{name: "struggle escalation pin keeps its own effort", model: flash, turn: turntype.MainLoop, reason: translate.ReasonStruggleEscalation, want: false},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			assert.Equal(t, tt.want, easyTierMinimalEffort(tt.model, tt.turn, tt.hardPin, tt.reason))
		})
	}
}

func TestEasyTierMinimalEffort_NoMenuModelsNeverForce(t *testing.T) {
	// A TierLow model whose menu has no levels (ReasoningEfforts empty) takes
	// no effort parameter at all — the "where the model supports it" clause.
	assert.False(t, easyTierMinimalEffort("unknown-tier-legacy-model", turntype.MainLoop, false, "cluster:v0.78"))
}
