package cluster

import (
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"aiand/router/internal/providers"
)

// The v0.78 incident: the overlay pipeline derived tier winners by raw
// quality argmax, ignoring the runtime blend's cost term. kimi-k3 — the most
// expensive model — took 7 clusters by raw argmax, but the served blend
// (alpha 0.96/0.8, cost term (1-alpha)*(1-cNorm)) strips all of them, so
// those clusters silently fell to motif-3 and routing collapsed to a
// monoculture. These tests pin the derivation rule the v0.79 overlay tool
// implements: the win-set map MUST be derived by running the exact runtime
// blend over the scaled tables, and raw-argmax and blend winners are NOT
// interchangeable.

// loadBundleScorer loads a committed bundle with a fake embedder matching
// its jina-v2 id/dim. blendScoresV2 never embeds, so no ONNX runtime is
// needed and the tests stay hermetic.
func loadBundleScorer(t *testing.T, version string) *Scorer {
	t.Helper()
	bundle, err := LoadBundle(version)
	require.NoError(t, err)
	require.Truef(t, bundle.IsV2, "%s must be a v2 bundle", version)
	s, err := NewScorer(bundle, DefaultConfig(), &fakeEmbedder{dim: bundle.Centroids.Dim}, map[string]struct{}{providers.ProviderAiand: {}})
	require.NoError(t, err)
	return s
}

// blendWinnerOf returns the per-cluster blend winner for a scorer's scaled
// tables — the same computation the v0.79 overlay tool performs at win-set
// derivation time (single-cluster argmax of blendScoresV2).
func blendWinnerOf(t *testing.T, s *Scorer, cluster int) string {
	t.Helper()
	knobs := s.defaultActiveKnobs()
	scores := s.blendScoresV2([]int{cluster}, knobs, s.models, nil, nil, 0)
	winner, _ := argmax(scores, s.models)
	require.NotEmptyf(t, winner, "cluster %d must have a winner", cluster)
	return winner
}

// rawQualityWinnerOf returns the per-cluster raw quality argmax — the WRONG
// derivation the v0.78 pipeline used.
func rawQualityWinnerOf(t *testing.T, s *Scorer, cluster int) string {
	t.Helper()
	row := s.qualityMeans[cluster]
	winner := ""
	best := float32(-1)
	for _, m := range s.models {
		if v := row[m]; v > best {
			best = v
			winner = m
		}
	}
	require.NotEmptyf(t, winner, "cluster %d must have a raw winner", cluster)
	return winner
}

// TestV078Incident_RawArgmaxDisagreesWithBlend pins the incident's core
// fact on the committed v0.78 bundle: on some clusters the raw quality
// argmax and the blend winner differ, and specifically the most expensive
// model (kimi-k3) wins clusters by raw argmax that the blend strips. If a
// future derivation ever reintroduces raw argmax, this test names the bug.
func TestV078Incident_RawArgmaxDisagreesWithBlend(t *testing.T) {
	s := loadBundleScorer(t, "v0.78")

	disagreements := 0
	rawKimiK3Wins := 0
	blendKimiK3Wins := 0
	for c := 0; c < s.centroids.K; c++ {
		raw := rawQualityWinnerOf(t, s, c)
		blend := blendWinnerOf(t, s, c)
		if raw != blend {
			disagreements++
		}
		if raw == "moonshotai/kimi-k3" {
			rawKimiK3Wins++
		}
		if blend == "moonshotai/kimi-k3" {
			blendKimiK3Wins++
		}
	}

	// Incident numbers: kimi-k3 raw-argmax wins 7/16, blend wins 0.
	assert.Equal(t, 7, rawKimiK3Wins,
		"v0.78 fixture: kimi-k3 must hold 7 raw-quality wins (the incident's derivation bug)")
	assert.Zero(t, blendKimiK3Wins,
		"v0.78 fixture: the served blend must strip every kimi-k3 raw win — the cost term owns this")
	assert.Greater(t, disagreements, 0,
		"raw argmax and blend winners must disagree on the incident fixture; if they always agreed the incident could not have happened")
}

// TestBlendWinnerMap_V078 pins the served v0.78 per-cluster blend winners —
// the monoculture this change exists to fix. Any accidental edit to v0.78
// tables would trip this and be visible at review.
func TestBlendWinnerMap_V078(t *testing.T) {
	s := loadBundleScorer(t, "v0.78")

	want := map[int]string{
		0: "zai-org/glm-5.3", 1: "motif-technologies/motif-3", 2: "moonshotai/kimi-k2.7-code",
		3: "motif-technologies/motif-3", 4: "motif-technologies/motif-3", 5: "motif-technologies/motif-3",
		6: "motif-technologies/motif-3", 7: "motif-technologies/motif-3", 8: "motif-technologies/motif-3",
		9: "motif-technologies/motif-3", 10: "motif-technologies/motif-3", 11: "moonshotai/kimi-k2.7-code",
		12: "motif-technologies/motif-3", 13: "zai-org/glm-5.3", 14: "motif-technologies/motif-3",
		15: "motif-technologies/motif-3",
	}
	for c, exp := range want {
		assert.Equalf(t, exp, blendWinnerOf(t, s, c), "v0.78 cluster %d winner", c)
	}
}
