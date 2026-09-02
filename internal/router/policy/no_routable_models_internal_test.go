package policy

import (
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestEmptyCandidateError_NoDiagnostics(t *testing.T) {
	assert.ErrorIs(t, emptyCandidateError(nil), ErrNoRoutableModels)
}

func TestCandidateLogFields_GroupsExclusionsByReason(t *testing.T) {
	fields := candidateLogFields(ResolvedCandidates{
		Candidates: []Candidate{{CatalogID: "gpt-4.1-mini"}, {CatalogID: "gemini-2.5-flash"}},
		Diagnostics: []Diagnostic{
			{CatalogID: "moonshotai/kimi-k3", Reason: ExclusionRequested},
			{CatalogID: "zai-org/glm-5.3", Reason: ExclusionContextWindow},
			{CatalogID: "deepseek-ai/deepseek-v4-flash", Reason: ExclusionRequested},
		},
	})

	assert.Equal(t, []any{
		"candidate_count", 2,
		"candidates", "gpt-4.1-mini,gemini-2.5-flash",
		"excluded_" + string(ExclusionContextWindow), "zai-org/glm-5.3",
		"excluded_" + string(ExclusionRequested), "deepseek-ai/deepseek-v4-flash,moonshotai/kimi-k3",
	}, fields)
}
