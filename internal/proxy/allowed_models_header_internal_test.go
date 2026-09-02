package proxy

import (
	"context"
	"testing"
	"time"

	"aiand/router/internal/providers"
	"aiand/router/internal/router"
	"aiand/router/internal/router/sessionpin"
	"aiand/router/internal/translate"

	"github.com/google/uuid"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

const (
	testGlm53 = "zai-org/glm-5.3"
	testKimi3 = "moonshotai/kimi-k3"
	testFlash = "deepseek-ai/deepseek-v4-flash"
)

func ctxWithRequestSubset(ctx context.Context, models ...string) context.Context {
	return context.WithValue(ctx, RequestAllowedModelsContextKey{}, RequestAllowedModels{Requested: models, Effective: models})
}

func TestParseAllowedModelsHeader_ResolvesAliasesAndDedupes(t *testing.T) {
	got, err := ParseAllowedModelsHeader(" z-ai/glm-5.3, moonshotai/kimi-k3 ,zai-org/glm-5.3,", nil)
	require.NoError(t, err)
	assert.Equal(t, []string{testGlm53, testKimi3}, got.Requested)
	assert.Equal(t, []string{testGlm53, testKimi3}, got.Effective)
}

func TestParseAllowedModelsHeader_UnknownAliasRejected(t *testing.T) {
	_, err := ParseAllowedModelsHeader("z-ai/glm-5.3,not-a-model", nil)
	var headerErr *AllowedModelsHeaderError
	require.ErrorAs(t, err, &headerErr)
	assert.Contains(t, headerErr.Reason, "not-a-model")
}

func TestParseAllowedModelsHeader_BlankRejected(t *testing.T) {
	_, err := ParseAllowedModelsHeader(" , ", nil)
	var headerErr *AllowedModelsHeaderError
	require.ErrorAs(t, err, &headerErr)
}

func TestParseAllowedModelsHeader_IntersectsInstallationAllowlist(t *testing.T) {
	got, err := ParseAllowedModelsHeader("z-ai/glm-5.3,moonshotai/kimi-k3", []string{testGlm53, testFlash})
	require.NoError(t, err)
	assert.Equal(t, []string{testGlm53, testKimi3}, got.Requested)
	assert.Equal(t, []string{testGlm53}, got.Effective)
}

func TestParseAllowedModelsHeader_EmptyIntersectionFailsClosed(t *testing.T) {
	_, err := ParseAllowedModelsHeader("moonshotai/kimi-k3", []string{testGlm53})
	var headerErr *AllowedModelsHeaderError
	require.ErrorAs(t, err, &headerErr)
	assert.Contains(t, headerErr.Reason, testKimi3)
}

func TestAllowedModelsForRequest_SubsetNarrowsPolicyAllowlist(t *testing.T) {
	ctx := ctxWithRequestSubset(ctxWithAllowedModels("a", "b"), "b", "c")
	assert.Equal(t, map[string]struct{}{"b": {}}, allowedModelsForRequest(ctx))
	assert.Equal(t, map[string]struct{}{"a": {}, "b": {}}, installationAllowedModelSet(ctx))
}

func TestAllowedModelsForRequest_SubsetAloneRestricts(t *testing.T) {
	ctx := ctxWithRequestSubset(context.Background(), "b")
	assert.Equal(t, map[string]struct{}{"b": {}}, allowedModelsForRequest(ctx))
	assert.Nil(t, installationAllowedModelSet(ctx))
}

func TestExcludedModelsForRequest_SubsetExcludesComplementButPolicySetDoesNot(t *testing.T) {
	s := &Service{availableModels: map[string]struct{}{"a": {}, "b": {}, "c": {}}}
	ctx := ctxWithRequestSubset(ctxWithAllowedModels("a", "b"), "b")

	got := s.excludedModelsForRequest(ctx)
	assert.NotContains(t, got, "b")
	assert.Contains(t, got, "a")
	assert.Contains(t, got, "c")

	policy := s.policyExcludedModels(ctx)
	assert.NotContains(t, policy, "a")
	assert.NotContains(t, policy, "b")
	assert.Contains(t, policy, "c")
}

func TestModelPermittedByAllowlist_IgnoresRequestSubset(t *testing.T) {
	ctx := ctxWithRequestSubset(ctxWithAllowedModels("a", "b"), "b")
	assert.True(t, modelPermittedByAllowlist(ctx, "a"))
	assert.False(t, modelPermittedByAllowlist(ctx, "c"))
}

func TestTelemetryDecisionReason_PrefixesOnlyWithSubset(t *testing.T) {
	assert.Equal(t, "cluster_argmax", telemetryDecisionReason(context.Background(), "cluster_argmax"))
	ctx := ctxWithRequestSubset(context.Background(), "b")
	assert.Equal(t, AllowlistOverrideReasonPrefix+"cluster_argmax", telemetryDecisionReason(ctx, "cluster_argmax"))
	assert.Equal(t, translate.ReasonUserForceModel, telemetryDecisionReason(ctx, translate.ReasonUserForceModel))
}

func TestRequestedAllowedModelsForTelemetry(t *testing.T) {
	assert.Nil(t, requestedAllowedModelsForTelemetry(context.Background()))
	ctx := context.WithValue(context.Background(), RequestAllowedModelsContextKey{}, RequestAllowedModels{
		Requested: []string{testKimi3, testGlm53},
		Effective: []string{testGlm53},
	})
	assert.Equal(t, []string{testKimi3, testGlm53}, requestedAllowedModelsForTelemetry(ctx))
}

func TestReadmitForcedModel_LiftsSubsetOnlyExclusion(t *testing.T) {
	s := &Service{availableModels: map[string]struct{}{testGlm53: {}, testKimi3: {}, testFlash: {}}}
	ctx := ctxWithRequestSubset(context.Background(), testGlm53)
	env, err := translate.ParseAnthropic([]byte(`{"model":"deepseek-ai/deepseek-v4-flash","max_tokens":16,"messages":[{"role":"user","content":"hi"}]}`))
	require.NoError(t, err)
	req := router.Request{ExcludedModels: s.excludedModelsForRequest(ctx)}
	require.Contains(t, req.ExcludedModels, testKimi3)

	pin := sessionpin.Pin{Model: testKimi3, Provider: providers.ProviderAiand}
	got := s.readmitForcedModel(ctx, req, env, translate.RoutingFeatures{MaxTokens: 16}, pin)
	assert.NotContains(t, got, testKimi3)
	assert.Contains(t, got, testFlash)
	assert.Contains(t, req.ExcludedModels, testKimi3, "input map must not be mutated")
}

func TestReadmitForcedModel_KeepsPolicyExclusion(t *testing.T) {
	s := &Service{availableModels: map[string]struct{}{testGlm53: {}, testKimi3: {}, testFlash: {}}}
	ctx := ctxWithRequestSubset(ctxWithAllowedModels(testGlm53, testKimi3), testGlm53)
	env, err := translate.ParseAnthropic([]byte(`{"model":"deepseek-ai/deepseek-v4-flash","max_tokens":16,"messages":[{"role":"user","content":"hi"}]}`))
	require.NoError(t, err)
	req := router.Request{ExcludedModels: s.excludedModelsForRequest(ctx)}

	pin := sessionpin.Pin{Model: testFlash, Provider: providers.ProviderAiand}
	got := s.readmitForcedModel(ctx, req, env, translate.RoutingFeatures{MaxTokens: 16}, pin)
	assert.Contains(t, got, testFlash)
}

func TestReadmitForcedModel_NoSubsetIsNoOp(t *testing.T) {
	s := &Service{availableModels: map[string]struct{}{testGlm53: {}, testKimi3: {}}}
	req := router.Request{ExcludedModels: map[string]struct{}{testKimi3: {}}}
	got := s.readmitForcedModel(context.Background(), req, nil, translate.RoutingFeatures{}, sessionpin.Pin{Model: testKimi3})
	assert.Contains(t, got, testKimi3)
}

func TestModelInRequestSubset(t *testing.T) {
	assert.True(t, modelInRequestSubset(context.Background(), testFlash))
	ctx := ctxWithRequestSubset(context.Background(), testGlm53)
	assert.True(t, modelInRequestSubset(ctx, testGlm53))
	assert.False(t, modelInRequestSubset(ctx, testFlash))
}

func TestForcedModelBinding_IgnoresRequestSubset(t *testing.T) {
	s := &Service{availableModels: map[string]struct{}{testGlm53: {}, testKimi3: {}, testFlash: {}}}
	ctx := ctxWithRequestSubset(ctxWithAllowedModels(testGlm53, testKimi3), testGlm53)

	binding, reason := s.forcedModelBinding(ctx, testKimi3, providers.ProviderAiand)
	assert.Empty(t, reason)
	assert.Equal(t, providers.ProviderAiand, binding)

	_, reason = s.forcedModelBinding(ctx, testFlash, providers.ProviderAiand)
	assert.NotEmpty(t, reason, "installation allowlist still binds a forced model")
}

// A sticky pin outside the request subset must reroute inside it; a pin
// inside the subset still sticks.
func TestTurnLoop_StickyPinOutsideRequestSubsetReroutes(t *testing.T) {
	newSvc := func(fr *tierProbeRouter) *Service {
		store := &overwritingPinStore{pin: sessionpin.Pin{
			Provider:    providers.ProviderAiand,
			Model:       testKimi3,
			Reason:      "cluster:v0.2",
			PinnedUntil: time.Now().Add(time.Hour),
		}, found: true}
		return NewService(fr, nil, nil, false, nil, store, false,
			providers.ProviderAiand, testFlash, nil).
			WithDeploymentKeyedProviders(keyed(providers.ProviderAiand))
	}
	env := forceCommandEnv(t)
	feats := env.RoutingFeatures(false)

	fr := &tierProbeRouter{available: map[string]struct{}{testKimi3: {}, testFlash: {}}}
	svc := newSvc(fr)
	ctx := ctxWithRequestSubset(context.Background(), testFlash)
	res, err := svc.runTurnLoop(ctx, env, feats, "key-1", uuid.New(), "", nil,
		router.Request{RequestedModel: feats.Model, ExcludedModels: svc.excludedModelsForRequest(ctx)})
	require.NoError(t, err)
	assert.Equal(t, testFlash, res.Decision.Model)
	assert.False(t, res.StickyHit)

	fr = &tierProbeRouter{available: map[string]struct{}{testKimi3: {}, testFlash: {}}}
	svc = newSvc(fr)
	ctx = ctxWithRequestSubset(context.Background(), testKimi3, testFlash)
	res, err = svc.runTurnLoop(ctx, env, feats, "key-1", uuid.New(), "", nil,
		router.Request{RequestedModel: feats.Model, ExcludedModels: svc.excludedModelsForRequest(ctx)})
	require.NoError(t, err)
	assert.Equal(t, testKimi3, res.Decision.Model)
}

func TestRequestAllowedModelsPresent(t *testing.T) {
	assert.False(t, requestAllowedModelsPresent(context.Background()))
	assert.True(t, requestAllowedModelsPresent(
		ctxWithRequestSubset(context.Background(), testGlm53)))
}
