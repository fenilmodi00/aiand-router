package proxy

import (
	"context"
	"fmt"
	"sync"
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

type forceModelMapStore struct {
	mu         sync.Mutex
	pins       map[string]sessionpin.Pin
	usageRoles []string
	usageKeys  [][sessionpin.SessionKeyLen]byte
}

func newForceModelMapStore() *forceModelMapStore {
	return &forceModelMapStore{pins: make(map[string]sessionpin.Pin)}
}

func forceModelMapKey(sessionKey [sessionpin.SessionKeyLen]byte, role string) string {
	return fmt.Sprintf("%x:%s", sessionKey, role)
}

func (s *forceModelMapStore) Get(_ context.Context, sessionKey [sessionpin.SessionKeyLen]byte, role string) (sessionpin.Pin, bool, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	pin, found := s.pins[forceModelMapKey(sessionKey, role)]
	return pin, found, nil
}

func (s *forceModelMapStore) Consume(_ context.Context, sessionKey [sessionpin.SessionKeyLen]byte, role string, expected router.Strategy) (sessionpin.Pin, bool, error) {
	s.mu.Lock()
	defer s.mu.Unlock()
	key := forceModelMapKey(sessionKey, role)
	pin, found := s.pins[key]
	if found && pin.PinnedUntil.After(time.Now()) && (pin.Strategy == expected || (pin.Strategy == "" && expected != router.StrategyHMMBeta)) {
		delete(s.pins, key)
		return pin, true, nil
	}
	return sessionpin.Pin{}, false, nil
}

func (s *forceModelMapStore) Upsert(_ context.Context, pin sessionpin.Pin) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	key := forceModelMapKey(pin.SessionKey, pin.Role)
	existing, found := s.pins[key]
	if found && existing.Strategy == pin.Strategy {
		pin.LastServedModel = existing.LastServedModel
		pin.LastTurnEndedAt = existing.LastTurnEndedAt
		pin.LastInputTokens = existing.LastInputTokens
		pin.LastOutputTokens = existing.LastOutputTokens
		pin.HasEverSwitched = existing.HasEverSwitched
	}
	s.pins[key] = pin
	return nil
}

func (s *forceModelMapStore) UpdateUsage(_ context.Context, sessionKey [sessionpin.SessionKeyLen]byte, role string, usage sessionpin.Usage) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	key := forceModelMapKey(sessionKey, role)
	pin, found := s.pins[key]
	if !found || (pin.Strategy != usage.Strategy && !(pin.Strategy == "" && usage.Strategy != router.StrategyHMMBeta)) {
		return nil
	}
	s.usageKeys = append(s.usageKeys, sessionKey)
	s.usageRoles = append(s.usageRoles, role)
	pin.LastServedModel = usage.ServedModel
	pin.LastTurnEndedAt = usage.EndedAt
	pin.LastInputTokens = usage.InputTokens
	pin.LastOutputTokens = usage.OutputTokens
	pin.HasEverSwitched = usage.SessionEverSwitched ||
		(usage.PriorServedModel != "" && usage.PriorServedModel != usage.ServedModel)
	s.pins[key] = pin
	return nil
}

func (*forceModelMapStore) IncrementUpstreamErrors(context.Context, [sessionpin.SessionKeyLen]byte, string, router.Strategy) (int, error) {
	return 0, nil
}
func (*forceModelMapStore) ResetUpstreamErrors(context.Context, [sessionpin.SessionKeyLen]byte, string, router.Strategy) error {
	return nil
}
func (*forceModelMapStore) IncrementOverloadErrors(context.Context, [sessionpin.SessionKeyLen]byte, string, router.Strategy) (int, error) {
	return 0, nil
}
func (*forceModelMapStore) ResetOverloadErrors(context.Context, [sessionpin.SessionKeyLen]byte, string, router.Strategy) error {
	return nil
}
func (*forceModelMapStore) DisableProvider(context.Context, [sessionpin.SessionKeyLen]byte, string, string, router.Strategy) error {
	return nil
}
func (*forceModelMapStore) SweepExpired(context.Context) error { return nil }

func TestRunTurnLoop_ForceModelSessionPinAppliesAcrossChildThreads(t *testing.T) {
	const (
		apiKeyID      = "api-key"
		clientSession = "client-session"
		forcedModel   = "moonshotai/kimi-k3"
	)
	installationID := uuid.New()
	ctx := context.WithValue(context.Background(), ClientIdentityContextKey{}, ClientIdentity{SessionID: clientSession})
	parent, err := translate.ParseAnthropic([]byte(`{
		"model":"deepseek-ai/deepseek-v4-flash",
		"messages":[{"role":"user","content":"parent task"}]
	}`))
	require.NoError(t, err)
	child, err := translate.ParseAnthropic([]byte(`{
		"model":"deepseek-ai/deepseek-v4-flash",
		"messages":[{"role":"user","content":"different child task"}]
	}`))
	require.NoError(t, err)

	parentThreadKey := deriveSessionKeyForRequest(ctx, parent, apiKeyID)
	childThreadKey := deriveSessionKeyForRequest(ctx, child, apiKeyID)
	forceSessionKey := deriveForceModelSessionKeyForRequest(ctx, parent, apiKeyID, parentThreadKey)
	require.NotEqual(t, parentThreadKey, childThreadKey)
	require.Equal(t, forceSessionKey, deriveForceModelSessionKeyForRequest(ctx, child, apiKeyID, childThreadKey))

	store := newForceModelMapStore()
	store.pins[forceModelMapKey(forceSessionKey, forceModelSessionRole)] = sessionpin.Pin{
		SessionKey:     forceSessionKey,
		Role:           forceModelSessionRole,
		InstallationID: installationID,
		Provider:       providers.ProviderAiand,
		Model:          forcedModel,
		Reason:         translate.ReasonUserForceModel,
		PinnedUntil:    pinNeverExpires,
	}
	freshRouter := &tierProbeRouter{available: map[string]struct{}{"deepseek-ai/deepseek-v4-flash": {}}}
	svc := NewService(freshRouter, nil, nil, false, nil, store, false,
		providers.ProviderAiand, "deepseek-ai/deepseek-v4-flash", nil)
	features := child.RoutingFeatures(false)

	ctx = router.WithStrategy(ctx, router.StrategyHMMBeta)
	result, err := svc.runTurnLoop(ctx, child, features, apiKeyID, installationID, "", nil, router.Request{
		RequestedModel: features.Model,
	})
	require.NoError(t, err)

	assert.Equal(t, forcedModel, result.Decision.Model)
	assert.Equal(t, translate.ReasonUserForceModel, result.Decision.Reason)
	assert.True(t, result.StickyHit)
	assert.False(t, result.HardPinned)
	assert.Equal(t, childThreadKey, result.SessionKey, "routing state must remain scoped to the child thread")
	assert.Equal(t, roleForTier(result.RequestedTier), result.PinRole)
	assert.Empty(t, freshRouter.captured, "session force must bypass the scorer")

	store.mu.Lock()
	defer store.mu.Unlock()
	_, controlStillPresent := store.pins[forceModelMapKey(forceSessionKey, forceModelSessionRole)]
	_, historyPresent := store.pins[forceModelMapKey(childThreadKey, forceModelHistoryRole(result.PinRole))]
	assert.True(t, controlStillPresent)
	assert.True(t, historyPresent)
	assert.Equal(t, pinNeverExpires, store.pins[forceModelMapKey(childThreadKey, forceModelHistoryRole(result.PinRole))].PinnedUntil)
}
