package proxy

import (
	"bufio"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"strings"
	"time"

	"aiand/router/internal/observability"
	"aiand/router/internal/providers"
	"aiand/router/internal/router"
	"aiand/router/internal/router/catalog"
	"aiand/router/internal/router/sessionpin"
	"aiand/router/internal/translate"

	"github.com/google/uuid"
)

// ForceModelHeader pins the session to a specific model, mirroring the
// /force-model chat command. Needed for headless clients (eval harness, CI
// smoke runs): Claude Code eats "/force-model …" as a client-side slash
// command before it reaches the router. The header rides on every request,
// so the pin is (re)written and served on the same turn. Values that name no
// catalog model fail the request; so do excluded ones.
const ForceModelHeader = "x-aiand-force-model"

// ErrForcedModelUnknown is returned when a caller forces a model name that
// resolves to no catalog entry. Failing is the point: routing on regardless
// serves a model the caller never asked for while looking like the force took.
var ErrForcedModelUnknown = errors.New("forced model is not a known model")

// ForcedModelUnknownError carries the unresolvable value so the dispatch
// classifier can quote it back.
type ForcedModelUnknownError struct {
	Model string
}

// Error implements error.
func (e *ForcedModelUnknownError) Error() string {
	return fmt.Sprintf("%q is not a known model", e.Model)
}

// Unwrap ties the typed error to ErrForcedModelUnknown for errors.Is.
func (e *ForcedModelUnknownError) Unwrap() error { return ErrForcedModelUnknown }

// forceModelAliases was deleted — vendor-family mappings were speculative
// and unsupported by the catalog. Unknown names fall through to prefix-based
// resolution in resolveForceModelWithEffort. Clients pinning a known catalog
// model use its full ID; partial vendor names go through the cluster scorer.
// ponytail: add back if a measurable caller base sends "claude" expecting
// zai-org/glm-5.2 resolves via alias, so the unknown-model rejection becomes a problem only for genuinely unknown names.

// resolveForceModelWithEffort strips a `:level` suffix and resolves the model
// to its canonical catalog ID. `known` is true only for exact catalog matches;
// known=false returns the implied provider from prefix hints (claude-*, gpt-*,
// gemini-*, /vendor/id) without pinning.
//
// Matching is exact: no prefix, substring, or nearest-match fallback.
func resolveForceModelWithEffort(model string) (canonicalID, provider string, known bool, effort string) {
	effortLevel, stripped := stripEffortSuffix(model)
	model = strings.ToLower(strings.TrimSpace(stripped))
	effort = effortLevel
	// Prefer an exact catalog / upstream hit before the openai/ prefix strip.
	if m, ok := catalog.ByIDOrUpstream(model); ok && len(m.Providers) > 0 {
		return m.ID, m.Providers[0].Provider, true, effort
	}
	unknownID := model
	if nativeID, ok := strings.CutPrefix(model, "openai/"); ok {
		model = nativeID
		unknownID = nativeID
	}
	// Second try after stripping openai/ prefix.
	if m, ok := catalog.ByIDOrUpstream(model); ok && len(m.Providers) > 0 {
		return m.ID, m.Providers[0].Provider, true, effort
	}
	// Unknown model: ai& is the only dispatchable upstream, so any binding a
	// caller forces resolves there (and fails there, with an honest upstream
	// unknown-model error rather than a synthetic provider mismatch).
	return unknownID, providers.ProviderAiand, false, effort
}

// resolveForceModel is the legacy two-return surface kept for backward compat.
func resolveForceModel(model string) (canonicalID, provider string, known bool) {
	canon, prov, kn, _ := resolveForceModelWithEffort(model)
	return canon, prov, kn
}

// stripEffortSuffix splits a `:level` suffix off model, canonicalizes it via
// CanonicalizeEffort, and returns ("", model) when no recognized suffix found.
func stripEffortSuffix(model string) (effort string, modelOut string) {
	const sep = ":"
	idx := strings.LastIndex(model, sep)
	if idx < 0 || idx == len(model)-1 {
		return "", model
	}
	tail := strings.TrimSpace(model[idx+1:])
	if !looksLikeEffortAlias(tail) {
		return "", model
	}
	return translate.CanonicalizeEffort(tail), model[:idx]
}

// looksLikeEffortAlias guards against future catalog IDs that contain `:`,
// ensuring the colon is only treated as a suffix separator for known levels.
func looksLikeEffortAlias(tail string) bool {
	switch strings.ToLower(strings.TrimSpace(tail)) {
	case "none", "disabled", "off", "fast", "low", "medium", "med", "high", "max", "xhigh",
		"ultra", "minimal", "min":
		return true
	default:
		return false
	}
}

const (
	forceModelSessionRole       = "force_model"
	forceModelHistoryRoleSuffix = "_force_hist"
	forceModelHistoryReason     = "force_model_history"
	userUnforcedReason          = "user_unforced"
)

func forceModelHistoryRole(role string) string {
	if role == "" {
		role = sessionpin.DefaultRole
	}
	return role + forceModelHistoryRoleSuffix
}

func (s *Service) preserveForceModelControlHistory(
	ctx context.Context,
	sessionKey [sessionpin.SessionKeyLen]byte,
	nextModel string,
) error {
	existing, found, err := s.pinStore.Get(ctx, sessionKey, forceModelSessionRole)
	if err != nil {
		return err
	}
	if !found || !isUserForcedReason(existing.Reason) || existing.Model == "" || existing.Model == nextModel {
		return nil
	}
	return s.pinStore.UpdateUsage(context.Background(), sessionKey, forceModelSessionRole, sessionpin.Usage{
		Strategy:            existing.Strategy,
		EndedAt:             time.Now(),
		ServedModel:         existing.Model,
		ServedProvider:      existing.Provider,
		PriorServedModel:    existing.LastServedModel,
		SessionEverSwitched: existing.HasEverSwitched,
	})
}

func (s *Service) setForceModelSessionPin(
	ctx context.Context,
	sessionKey [sessionpin.SessionKeyLen]byte,
	installationID uuid.UUID,
	canonicalModel, provider string,
) error {
	if s.pinStore == nil || installationID == uuid.Nil {
		return nil
	}
	if err := s.preserveForceModelControlHistory(ctx, sessionKey, canonicalModel); err != nil {
		return fmt.Errorf("preserve force-model control history: %w", err)
	}
	forced := sessionpin.Pin{
		SessionKey:     sessionKey,
		Role:           forceModelSessionRole,
		InstallationID: installationID,
		Provider:       provider,
		Model:          canonicalModel,
		Reason:         translate.ReasonUserForceModel,
		TurnCount:      1,
		PinnedUntil:    pinNeverExpires,
	}
	return s.pinStore.Upsert(context.Background(), forced)
}

func (s *Service) loadForceModelSessionPin(
	ctx context.Context,
	sessionKey [sessionpin.SessionKeyLen]byte,
) (sessionpin.Pin, bool, bool) {
	if s.pinStore == nil {
		return sessionpin.Pin{}, false, false
	}
	pin, found, err := s.pinStore.Get(ctx, sessionKey, forceModelSessionRole)
	if err != nil {
		observability.FromContext(ctx).Error("force-model session pin lookup failed", "err", err)
		return sessionpin.Pin{}, false, false
	}
	if found && pin.Reason == userUnforcedReason {
		return pin, false, true
	}
	if !found || !pin.PinnedUntil.After(time.Now()) || !isUserForcedReason(pin.Reason) || pin.Model == "" || pin.Provider == "" {
		return sessionpin.Pin{}, false, false
	}
	return pin, true, false
}

func (s *Service) loadForceModelHistory(
	ctx context.Context,
	sessionKey [sessionpin.SessionKeyLen]byte,
	role string,
) sessionpin.Pin {
	if s.pinStore == nil {
		return sessionpin.Pin{}
	}
	pin, found, err := s.pinStore.Get(ctx, sessionKey, forceModelHistoryRole(role))
	if err != nil {
		observability.FromContext(ctx).Error("force-model history lookup failed", "err", err)
		return sessionpin.Pin{}
	}
	if !found || !pin.PinnedUntil.After(time.Now()) {
		return sessionpin.Pin{}
	}
	return pin
}

func (s *Service) anchorForceModelHistory(
	ctx context.Context,
	installationID uuid.UUID,
	sessionKey [sessionpin.SessionKeyLen]byte,
	role string,
	forcedPin sessionpin.Pin,
) {
	if s.pinStore == nil || installationID == uuid.Nil {
		return
	}
	s.upsertPin(ctx, sessionpin.Pin{
		SessionKey:     sessionKey,
		Role:           forceModelHistoryRole(role),
		InstallationID: installationID,
		Provider:       forcedPin.Provider,
		Model:          forcedPin.Model,
		Reason:         forceModelHistoryReason,
		Strategy:       router.StrategyFromContext(ctx),
		TurnCount:      1,
		PinnedUntil:    pinNeverExpires,
	})
}

func forceModelClearRoles() []string {
	return []string{
		roleForTier(catalog.TierUnknown),
		roleForTier(catalog.TierLow),
		roleForTier(catalog.TierMid),
		roleForTier(catalog.TierHigh),
	}
}

func (s *Service) clearLegacyForceModelPins(
	ctx context.Context,
	installationID uuid.UUID,
	sessionKey [sessionpin.SessionKeyLen]byte,
) error {
	if s.pinStore == nil || installationID == uuid.Nil {
		return nil
	}
	for _, role := range forceModelClearRoles() {
		pin, found, err := s.pinStore.Get(ctx, sessionKey, role)
		if err != nil {
			return fmt.Errorf("load legacy force-model pin for role %q: %w", role, err)
		}
		if !found || !isUserForcedReason(pin.Reason) {
			continue
		}
		if err := s.expireSessionPin(ctx, installationID, sessionKey, role, userUnforcedReason); err != nil {
			return err
		}
	}
	return nil
}

func (s *Service) clearForceModelSessionPin(
	ctx context.Context,
	installationID uuid.UUID,
	sessionKey [sessionpin.SessionKeyLen]byte,
) error {
	if s.pinStore == nil || installationID == uuid.Nil {
		return nil
	}
	if err := s.preserveForceModelControlHistory(ctx, sessionKey, ""); err != nil {
		return fmt.Errorf("preserve force-model control history before clear: %w", err)
	}
	cleared := sessionpin.Pin{
		SessionKey:     sessionKey,
		Role:           forceModelSessionRole,
		InstallationID: installationID,
		Reason:         userUnforcedReason,
		TurnCount:      1,
		PinnedUntil:    pinNeverExpires,
	}
	return s.pinStore.Upsert(context.Background(), cleared)
}

// previewForceModelFromRequest resolves force intent for decision-only route
// endpoints (/v1/route, playground preview). Only resolvable model fields or
// x-aiand-force-model force; unknown client passthrough names (e.g.
// claude-sonnet-4-20250514) leave ForceModel empty so cluster routing proceeds.
// Resolve-only — never writes a pin.
func previewForceModelFromRequest(headers http.Header, env *translate.RequestEnvelope) (string, error) {
	raw := rawForceModelFromHeaders(headers, env)
	if raw == "" {
		return "", nil
	}
	canonicalModel, _, known, _ := resolveForceModelWithEffort(raw)
	if !known {
		return "", &ForcedModelUnknownError{Model: raw}
	}
	return canonicalModel, nil
}

// isWireCompatPassthroughModel classifies a non-catalog model as a wire-compat
// name the client sent for provider API compatibility, not router routing
// intent: the claude-* and gemini-* families on both surfaces. The aiand
// installer writes claude-opus-5/claude-sonnet-4-6 style ids into models.json,
// so rejecting them would break installs; they route via the cluster silently
// when they resolve to no catalog row — intentional aliasing documented in
// docs/CONFIGURATION.md. The OpenAI gpt-*/o* families are NOT passthrough:
// unknown names there are routing intent and fail (see
// rawForceModelFromHeaders). The old `HasPrefix(model, "o")` matched every
// o-word (opus, offline, …) and silently rerouted them; that broad match is
// gone.
func isWireCompatPassthroughModel(model string) bool {
	model = strings.ToLower(strings.TrimSpace(model))
	return strings.HasPrefix(model, "claude-") || strings.HasPrefix(model, "gemini-")
}

// rawForceModelFromHeaders picks the raw force-model string from the inbound
// model field and x-aiand-force-model header. A catalog-resolvable, non-auto
// model field wins over a conflicting header; model=auto, empty, wire-compat
// passthrough, or unknown vendor/id slugs defer to the header; unknown bare
// names — including the gpt-*/o* OpenAI family — are explicit routing intent
// and fail when not in the catalog.
func rawForceModelFromHeaders(headers http.Header, env *translate.RequestEnvelope) string {
	bodyModel, _ := translate.CanonicalModel(env.Model())
	bodyModel = strings.TrimSpace(bodyModel)
	if bodyModel != "" && bodyModel != "auto" {
		if _, _, known, _ := resolveForceModelWithEffort(bodyModel); known {
			return bodyModel
		}
		if isWireCompatPassthroughModel(bodyModel) || strings.Contains(bodyModel, "/") {
			return ""
		}
		return bodyModel
	}
	if headers == nil {
		return ""
	}
	return strings.TrimSpace(headers.Get(ForceModelHeader))
}

// mergeForceEffortKnobs stashes effortLevel on the request context as
// router.Overrides.ForceEffort without dropping other routing knobs.
func mergeForceEffortKnobs(r *http.Request, effortLevel string) {
	if effortLevel == "" {
		return
	}
	merged := router.Overrides{ForceEffort: effortLevel}
	if existing := router.RoutingKnobsFromContext(r.Context()); existing != nil {
		merged.Alpha = existing.Alpha
		merged.QualityBias = existing.QualityBias
		merged.SpeedWeight = existing.SpeedWeight
		merged.OutputCostRatio = existing.OutputCostRatio
		merged.ExpectedOutputTokens = existing.ExpectedOutputTokens
		merged.PerModelVerbosity = existing.PerModelVerbosity
	}
	*r = *r.WithContext(router.WithRoutingKnobs(r.Context(), &merged))
}

// applyResolvedForceModel resolves raw, writes the session pin, and returns
// the canonical catalog id. logLabel names the source in log lines
// ("force-model", "x-aiand-force-model").
func (s *Service) applyResolvedForceModel(
	ctx context.Context,
	r *http.Request,
	installationID uuid.UUID,
	forceModelSessionKey [sessionpin.SessionKeyLen]byte,
	raw, logLabel string,
) (string, error) {
	log := observability.FromContext(ctx)
	canonicalModel, provider, known, effortLevel := resolveForceModelWithEffort(raw)
	mergeForceEffortKnobs(r, effortLevel)
	if !known {
		log.Warn(logLabel+": rejected unrecognized model",
			"input_model", raw,
			"force_model_session_key_hex", fmt.Sprintf("%x", forceModelSessionKey),
		)
		return "", &ForcedModelUnknownError{Model: raw}
	}
	binding, reason := s.forcedModelBinding(ctx, canonicalModel, provider)
	if reason != "" {
		log.Warn(logLabel+": rejected excluded model",
			"input_model", raw,
			"canonical_model", canonicalModel,
			"provider", provider,
			"reason", reason,
		)
		return "", &ForcedModelExcludedError{Model: canonicalModel, Reason: reason}
	}
	provider = binding
	if err := s.setForceModelSessionPin(ctx, forceModelSessionKey, installationID, canonicalModel, provider); err != nil {
		log.Error(logLabel+": session pin upsert failed", "err", err)
		return canonicalModel, nil
	}
	log.Info(logLabel+" applied",
		"input_model", raw,
		"canonical_model", canonicalModel,
		"provider", provider,
		"effort", effortLevel,
		"force_model_session_key_hex", fmt.Sprintf("%x", forceModelSessionKey),
		"role", forceModelSessionRole,
	)
	return canonicalModel, nil
}

// applyForceModel honors force intent from the inbound model field and the
// x-aiand-force-model header, writing the same session pin the /force-model
// command writes. A resolvable model field beats a conflicting header;
// model=auto or empty defers to the header.
func (s *Service) applyForceModel(
	ctx context.Context,
	r *http.Request,
	env *translate.RequestEnvelope,
	installationID uuid.UUID,
	threadSessionKey, forceModelSessionKey [sessionpin.SessionKeyLen]byte,
) (string, error) {
	raw := rawForceModelFromHeaders(r.Header, env)
	if raw == "" {
		return "", nil
	}
	return s.applyResolvedForceModel(ctx, r, installationID, forceModelSessionKey, raw, "force-model")
}

// applyForceModelHeader honors only the x-aiand-force-model request header.
func (s *Service) applyForceModelHeader(
	ctx context.Context,
	r *http.Request,
	installationID uuid.UUID,
	forceModelSessionKey [sessionpin.SessionKeyLen]byte,
) (string, error) {
	raw := strings.TrimSpace(r.Header.Get(ForceModelHeader))
	if raw == "" {
		return "", nil
	}
	return s.applyResolvedForceModel(ctx, r, installationID, forceModelSessionKey, raw, "x-aiand-force-model")
}

// handleForceModelCommand processes a /force-model or /unforce-model directive:
// writes (or expires) the session pin and returns a synthetic acknowledgment
// response without dispatching upstream. inputTokens should be the request's
// RoutingFeatures.Tokens so the token counter reflects actual turn input, not
// just the synthetic response text.
func (s *Service) handleForceModelCommand(
	ctx context.Context,
	w http.ResponseWriter,
	env *translate.RequestEnvelope,
	cmd translate.ForceModelResult,
	installationID uuid.UUID,
	threadSessionKey, forceModelSessionKey [sessionpin.SessionKeyLen]byte,
	inputTokens int,
) error {
	_, msg, err := s.applyForceModelCommand(ctx, env, cmd, installationID, threadSessionKey, forceModelSessionKey)
	if err != nil {
		return err
	}
	switch env.SourceFormat() {
	case translate.FormatOpenAI:
		return writeSyntheticOpenAIResponse(w, env, msg, inputTokens)
	default:
		return writeSyntheticAnthropicResponse(w, env, msg, inputTokens)
	}
}

// applyForceModelCommand updates the session pin without deciding whether the
// caller should receive a synthetic response. It returns the canonical model
// when a force was applied.
func (s *Service) applyForceModelCommand(
	ctx context.Context,
	env *translate.RequestEnvelope,
	cmd translate.ForceModelResult,
	installationID uuid.UUID,
	threadSessionKey, forceModelSessionKey [sessionpin.SessionKeyLen]byte,
) (string, string, error) {
	log := observability.FromContext(ctx)

	var msg string
	if cmd.Clear {
		if err := s.clearLegacyForceModelPins(ctx, installationID, threadSessionKey); err != nil {
			log.Error("/unforce-model: legacy pin cleanup failed", "err", err)
			return "", "", err
		}
		if err := s.clearForceModelSessionPin(ctx, installationID, forceModelSessionKey); err != nil {
			log.Error("/unforce-model: session pin clear failed", "err", err)
			return "", "", err
		}
		msg = "✦ **Aiand Router** → force-model cleared · resuming automatic model selection\n\n"
		if env.SourceFormat() == translate.FormatOpenAI {
			msg = "Aiand Router: force-model cleared; resuming automatic model selection"
		}
		log.Debug("/unforce-model: session pin cleared",
			"force_model_session_key_hex", fmt.Sprintf("%x", forceModelSessionKey),
			"role", forceModelSessionRole,
		)
		return "", msg, nil
	}

	canonicalModel, provider, known := resolveForceModel(cmd.Model)
	if !known {
		log.Info("/force-model: rejected unknown model",
			"input_model", cmd.Model,
			"force_model_session_key_hex", fmt.Sprintf("%x", forceModelSessionKey),
			"role", forceModelSessionRole,
		)
		msg = fmt.Sprintf("✦ **Aiand Router** → force-model: %q isn't a recognized model · keeping automatic routing. Use a full model ID, e.g. moonshotai/kimi-k3, deepseek-ai/deepseek-v4-flash, or zai-org/glm-5.3.\n\n", cmd.Model)
		if env.SourceFormat() == translate.FormatOpenAI {
			msg = fmt.Sprintf("Aiand Router: force-model: %q isn't a recognized model; keeping automatic routing. Use a full model ID, e.g. moonshotai/kimi-k3, deepseek-ai/deepseek-v4-flash, or zai-org/glm-5.3.", cmd.Model)
		}
		return "", msg, nil
	}

	binding, reason := s.forcedModelBinding(ctx, canonicalModel, provider)
	if reason != "" {
		log.Warn("/force-model: rejected excluded model",
			"input_model", cmd.Model,
			"canonical_model", canonicalModel,
			"provider", provider,
			"reason", reason,
			"force_model_session_key_hex", fmt.Sprintf("%x", forceModelSessionKey),
			"role", forceModelSessionRole,
		)
		msg = fmt.Sprintf("✦ **Aiand Router** → force-model rejected: %s · keeping automatic routing. Ask an admin to allow the provider, or force a model from one that is permitted.\n\n", reason)
		if env.SourceFormat() == translate.FormatOpenAI {
			msg = fmt.Sprintf("Aiand Router: force-model rejected: %s; keeping automatic routing. Ask an admin to allow the provider, or force a model from one that is permitted.", reason)
		}
		return "", msg, nil
	}

	if err := s.clearLegacyForceModelPins(ctx, installationID, threadSessionKey); err != nil {
		log.Error("/force-model: legacy pin cleanup failed", "err", err)
		return "", "", err
	}
	if err := s.setForceModelSessionPin(ctx, forceModelSessionKey, installationID, canonicalModel, binding); err != nil {
		log.Error("/force-model: session pin upsert failed", "err", err)
		return "", "", err
	}
	msg = fmt.Sprintf("✦ **Aiand Router** → force-model applied: %s (%s) · Use /unforce-model to clear\n\n", canonicalModel, binding)
	if env.SourceFormat() == translate.FormatOpenAI {
		msg = fmt.Sprintf("Aiand Router: force-model applied: %s (%s). Use /unforce-model to clear.", canonicalModel, binding)
	}
	log.Debug("/force-model: session pin set",
		"input_model", cmd.Model,
		"canonical_model", canonicalModel,
		"provider", binding,
		"force_model_session_key_hex", fmt.Sprintf("%x", forceModelSessionKey),
		"role", forceModelSessionRole,
	)
	return canonicalModel, msg, nil
}

// writeSyntheticAnthropicResponse writes a minimal Anthropic Messages API
// response without hitting an upstream, handling both streaming and
// non-streaming shapes.
func writeSyntheticAnthropicResponse(w http.ResponseWriter, env *translate.RequestEnvelope, text string, inputTokens int) error {
	msgID := fmt.Sprintf("msg_router_cmd_%x", time.Now().UnixNano())
	if env.Stream() {
		return writeSyntheticAnthropicSSE(w, msgID, text, inputTokens)
	}
	return writeSyntheticAnthropicJSON(w, msgID, text, inputTokens)
}

func writeSyntheticAnthropicJSON(w http.ResponseWriter, msgID, text string, inputTokens int) error {
	resp := map[string]any{
		"id":            msgID,
		"type":          "message",
		"role":          "assistant",
		"model":         "aiand-router",
		"stop_reason":   "end_turn",
		"stop_sequence": nil,
		"content": []any{
			map[string]any{"type": "text", "text": text},
		},
		"usage": map[string]any{
			"input_tokens":  inputTokens,
			"output_tokens": len(text) / 4,
		},
	}
	body, err := json.Marshal(resp)
	if err != nil {
		return fmt.Errorf("marshal synthetic response: %w", err)
	}
	w.Header().Set("Content-Type", "application/json")
	_, writeErr := w.Write(body)
	return writeErr
}

func writeSyntheticAnthropicSSE(w http.ResponseWriter, msgID, text string, inputTokens int) error {
	w.Header().Set("Content-Type", "text/event-stream")
	flusher, _ := w.(http.Flusher)
	bw := bufio.NewWriterSize(w, 4096)

	outTokens := len(text) / 4

	events := []string{
		sseEvent("message_start", mustMarshalJSON(map[string]any{
			"type": "message_start",
			"message": map[string]any{
				"id": msgID, "type": "message", "role": "assistant",
				"content": []any{}, "model": "aiand-router",
				"stop_reason": nil, "stop_sequence": nil,
				"usage": map[string]any{"input_tokens": inputTokens, "output_tokens": 0},
			},
		})),
		sseEvent("content_block_start", mustMarshalJSON(map[string]any{
			"type": "content_block_start", "index": 0,
			"content_block": map[string]any{"type": "text", "text": ""},
		})),
		sseEvent("ping", `{"type":"ping"}`),
		sseEvent("content_block_delta", mustMarshalJSON(map[string]any{
			"type": "content_block_delta", "index": 0,
			"delta": map[string]any{"type": "text_delta", "text": text},
		})),
		sseEvent("content_block_stop", `{"type":"content_block_stop","index":0}`),
		sseEvent("message_delta", mustMarshalJSON(map[string]any{
			"type":  "message_delta",
			"delta": map[string]any{"stop_reason": "end_turn", "stop_sequence": nil},
			"usage": map[string]any{"output_tokens": outTokens},
		})),
		sseEvent("message_stop", `{"type":"message_stop"}`),
	}

	for _, ev := range events {
		bw.WriteString(ev)
	}
	if err := bw.Flush(); err != nil {
		return err
	}
	if flusher != nil {
		flusher.Flush()
	}
	return nil
}

// writeSyntheticOpenAIResponse writes a minimal OpenAI Chat Completions
// response without hitting an upstream, handling both streaming and
// non-streaming shapes.
func writeSyntheticOpenAIResponse(w http.ResponseWriter, env *translate.RequestEnvelope, text string, inputTokens int) error {
	respID := fmt.Sprintf("chatcmpl_router_cmd_%x", time.Now().UnixNano())
	if env.Stream() {
		return writeSyntheticOpenAISSE(w, respID, text, inputTokens)
	}
	return writeSyntheticOpenAIJSON(w, respID, text, inputTokens)
}

func writeSyntheticOpenAIJSON(w http.ResponseWriter, respID, text string, inputTokens int) error {
	outTokens := len(text) / 4
	resp := map[string]any{
		"id":      respID,
		"object":  "chat.completion",
		"created": time.Now().Unix(),
		"model":   "aiand-router",
		"choices": []any{
			map[string]any{
				"index": 0,
				"message": map[string]any{
					"role":    "assistant",
					"content": text,
				},
				"finish_reason": "stop",
			},
		},
		"usage": map[string]any{
			"prompt_tokens":     inputTokens,
			"completion_tokens": outTokens,
			"total_tokens":      inputTokens + outTokens,
		},
	}
	body, err := json.Marshal(resp)
	if err != nil {
		return fmt.Errorf("marshal synthetic openai response: %w", err)
	}
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	_, writeErr := w.Write(body)
	return writeErr
}

func writeSyntheticOpenAISSE(w http.ResponseWriter, respID, text string, inputTokens int) error {
	w.Header().Set("Content-Type", "text/event-stream")
	w.WriteHeader(http.StatusOK)
	flusher, _ := w.(http.Flusher)
	bw := bufio.NewWriterSize(w, 4096)
	created := time.Now().Unix()
	outTokens := len(text) / 4
	chunkStart := mustMarshalJSON(map[string]any{
		"id":      respID,
		"object":  "chat.completion.chunk",
		"created": created,
		"model":   "aiand-router",
		"choices": []any{
			map[string]any{
				"index": 0,
				"delta": map[string]any{
					"role":    "assistant",
					"content": text,
				},
				"finish_reason": nil,
			},
		},
	})
	chunkStop := mustMarshalJSON(map[string]any{
		"id":      respID,
		"object":  "chat.completion.chunk",
		"created": created,
		"model":   "aiand-router",
		"choices": []any{
			map[string]any{
				"index":         0,
				"delta":         map[string]any{},
				"finish_reason": "stop",
			},
		},
		"usage": map[string]any{
			"prompt_tokens":     inputTokens,
			"completion_tokens": outTokens,
			"total_tokens":      inputTokens + outTokens,
		},
	})
	events := []string{
		openAISSEData(chunkStart),
		openAISSEData(chunkStop),
		openAISSEData("[DONE]"),
	}
	for _, ev := range events {
		bw.WriteString(ev)
	}
	if err := bw.Flush(); err != nil {
		return err
	}
	if flusher != nil {
		flusher.Flush()
	}
	return nil
}

func sseEvent(eventType, data string) string {
	return "event: " + eventType + "\ndata: " + data + "\n\n"
}

func openAISSEData(data string) string {
	return "data: " + data + "\n\n"
}

func mustMarshalJSON(v any) string {
	b, err := json.Marshal(v)
	if err != nil {
		return "{}"
	}
	return string(b)
}
