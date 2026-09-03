package proxy

import (
	"context"
	"errors"
	"fmt"
	"net/http"

	"aiand/router/internal/observability"
	"aiand/router/internal/providers"
	"aiand/router/internal/router"
	"aiand/router/internal/router/catalog"
	"aiand/router/internal/router/handover"
	"aiand/router/internal/router/sessionpin"
	"aiand/router/internal/router/turntype"
	"aiand/router/internal/translate"
)

// ErrContextWindowExceeded is returned after the full compaction cascade
// (tool-result cleanup, summarization, trim) still can't fit any eligible
// model's window. Maps to HTTP 413, distinct from ErrNoEligibleProvider.
var ErrContextWindowExceeded = errors.New("proxy: request context exceeds every eligible model's window")

const (
	// DefaultCompactionTriggerPct is the fraction of the largest eligible
	// model's window at which the cascade engages. Compacting below the window
	// (not at overflow) keeps the pre-summary history small enough for a
	// summarizer to ingest.
	DefaultCompactionTriggerPct = 0.85
	// DefaultCompactionModel is the model the cascade summarizes with when the
	// session has no warm pin to reuse. Mid-tier: the compaction summary is
	// the only record of the elided history, so it is worth a mid-tier model.
	// Overridable via ROUTER_COMPACTION_MODEL.
	DefaultCompactionModel = "motif-technologies/motif-3"
	// compactionSummaryOutputReserve is headroom (summary output + margin) the
	// selected summarizer model needs above the history it must ingest.
	compactionSummaryOutputReserve = DefaultCompactionMaxTokens + 8_000
	// largeWindowSummarizerModel is the big-context aiand catalog model used
	// to summarize histories too large for the default summarizer.
	largeWindowSummarizerModel = "moonshotai/kimi-k3"
	// claudeCodeAutoCompactBuffer is the token headroom below its believed
	// context window at which Claude Code's own auto-compact fires. Mirrors
	// the client (2.1.x) so the router can tell whether the client would have
	// compacted this history itself.
	claudeCodeAutoCompactBuffer = 13_000
)

// compactionPolicy is the per-harness shape of the compaction cascade. Each
// coding harness trims history differently (Claude Code auto-compacts against
// the requested model's window; Codex sends its transcripts verbatim), so the
// router's proactive cascade is tuned per client rather than one-size-fits-all.
type compactionPolicy struct {
	// RecentTurns is how many trailing non-system messages survive a
	// summarization rewrite, so the model keeps immediate working context.
	RecentTurns int
	// ToolResultKeep is how many trailing tool results Tier-1 cleanup leaves
	// intact; older ones are replaced with a placeholder.
	ToolResultKeep int
	// DeferToClient marks a harness that auto-compacts on its own against the
	// requested model's context window. The router then only compacts when
	// the routable pool's largest window is smaller than what the client
	// believes it has — otherwise the client's own compaction (on its own
	// model, with a warm prompt cache) fires first and does a better job.
	DeferToClient bool
	// ClientBuffer is the token headroom below the requested model's window
	// at which the deferring client compacts itself.
	ClientBuffer int
}

var (
	defaultCompactionPolicy = compactionPolicy{RecentTurns: 12, ToolResultKeep: 5}

	compactionPolicies = map[string]compactionPolicy{
		ClientAppClaudeCode: {RecentTurns: 12, ToolResultKeep: 5, DeferToClient: true, ClientBuffer: claudeCodeAutoCompactBuffer},
		ClientAppCodex:      {RecentTurns: 12, ToolResultKeep: 5},
		ClientAppGeminiCLI:  {RecentTurns: 12, ToolResultKeep: 5},
	}
)

// compactionPolicyFor returns the harness policy for a canonical client_app
// (ClientIdentity.ClientApp), or the default for unknown/absent clients.
func compactionPolicyFor(clientApp string) compactionPolicy {
	if p, ok := compactionPolicies[clientApp]; ok {
		return p
	}
	return defaultCompactionPolicy
}

// CompactionSummarizer summarizes prior conversation with the structured
// compaction prompt against an explicit model. Implemented by
// *ProviderSummarizer; declared here so the Service depends on the behavior,
// not the concrete type.
type CompactionSummarizer interface {
	SummarizeForCompaction(ctx context.Context, env *translate.RequestEnvelope, model string, maxTokens int) (string, handover.Usage, error)
	Provider() string
}

// compactionInput is the per-request context the cascade decides against.
type compactionInput struct {
	TurnType      turntype.TurnType
	OutputReserve int
	// MaxWindow is the largest effective context window among eligible
	// routing models (maxEligibleContextWindow). Zero disables the cascade.
	MaxWindow int
	// RequestedModel is the client-requested model; a deferring harness sizes
	// its own compaction against this model's window.
	RequestedModel string
	// ClientApp selects the harness policy (ClientIdentity.ClientApp).
	ClientApp string
	// PreferredSummarizer resolves the session's pinned model when there is
	// one worth reusing (compactionPreferredSummarizer). Invoked only once
	// the cascade actually needs a summarizer, so the common below-threshold
	// turn costs no extra pin-store read. Nil means none.
	PreferredSummarizer func() string
	Headers             http.Header
}

// compactionResult records what the cascade did, for logging and billing.
type compactionResult struct {
	Applied            bool
	ToolResultsCleared int
	Summarized         bool
	SummaryModel       string
	SummaryUsage       handover.Usage
	TrimmedToRecent    int
	FinalEstimate      int
	// DeferredToClient is true when the harness policy left compaction to the
	// client because the routable pool can serve the window it believes in.
	DeferredToClient bool
}

// maxEligibleContextWindow returns the largest effective context window among
// available routing models that are not policy-excluded. It uses the smallest
// enabled binding window for each model, matching the overflow pre-filter's
// conservative dispatch check: compaction must not stop because a fallback
// binding has more capacity than the binding that can actually serve first.
// A signature-stripping (non-Anthropic) target gets sigSavings added to its
// window, mirroring excludeContextOverflowModels. Zero when none are known
// (availableModels unset), which disables compaction.
func (s *Service) maxEligibleContextWindow(policyExcluded, enabledProviders map[string]struct{}, sigSavings int) int {
	maxWindow := 0
	for model := range s.availableModels {
		if _, excluded := policyExcluded[model]; excluded {
			continue
		}
		w := minContextWindowForModel(model, enabledProviders)
		if sigSavings > 0 && modelStripsAnthropicSignatures(model) {
			w += sigSavings
		}
		if w > maxWindow {
			maxWindow = w
		}
	}
	return maxWindow
}

// compactionModelOrDefault returns the configured mid-tier summarizer.
func (s *Service) compactionModelOrDefault() string {
	if s.compactionModel != "" {
		return s.compactionModel
	}
	return DefaultCompactionModel
}

// summarizerEligible reports whether model is a catalog model the
// ProviderSummarizer can dispatch to, and is not a low-tier model (a
// low-tier summary is what the cascade is moving away from).
func summarizerEligible(model string) bool {
	m, ok := catalog.ByID(model)
	if !ok || m.Tier == catalog.TierLow {
		return false
	}
	return len(m.Providers) > 0
}

// compactionSummarizerCandidates orders the models the cascade may summarize
// with: the session's warm pin first (the model that saw the conversation,
// mirroring a client's own-model compaction), then the configured mid-tier
// default, then the large-window model.
func (s *Service) compactionSummarizerCandidates(preferred string) []string {
	out := make([]string, 0, 3)
	seen := map[string]struct{}{}
	add := func(m string) {
		if m == "" {
			return
		}
		if _, dup := seen[m]; dup {
			return
		}
		seen[m] = struct{}{}
		out = append(out, m)
	}
	if summarizerEligible(preferred) {
		add(preferred)
	}
	add(s.compactionModelOrDefault())
	add(largeWindowSummarizerModel)
	return out
}

// selectCompactionSummarizer returns the first candidate summarizer model
// whose context window can ingest historyTokens plus summary headroom, or ""
// when none can (caller falls back to trimming).
func (s *Service) selectCompactionSummarizer(historyTokens int, preferred string) string {
	need := historyTokens + compactionSummaryOutputReserve
	for _, m := range s.compactionSummarizerCandidates(preferred) {
		if catalog.ContextWindowFor(m) >= need {
			return m
		}
	}
	return ""
}

// compactionPreferredSummarizer returns the session's active pinned model
// when it is eligible for summarization — the same model that has been
// running the conversation, so its prompt cache is warm for the summary call.
// Empty when there is no pin store, no active pin, or the pin is ineligible.
func (s *Service) compactionPreferredSummarizer(ctx context.Context, sessionKey [sessionpin.SessionKeyLen]byte, role string) string {
	if s.pinStore == nil {
		return ""
	}
	pin, active := s.loadPin(ctx, sessionKey, role)
	if !active || !summarizerEligible(pin.Model) {
		return ""
	}
	return pin.Model
}

// clientWouldCompact reports whether a deferring harness's own auto-compact
// would fire on this history before the router's cascade is needed: the
// routable pool can serve the window the client believes it has, so the
// request will still fit an eligible model when the client compacts at
// (requested window - ClientBuffer).
func clientWouldCompact(pol compactionPolicy, requestedModel string, maxWindow int) bool {
	if !pol.DeferToClient || requestedModel == "" {
		return false
	}
	clientWindow := catalog.ContextWindowFor(requestedModel)
	return clientWindow-pol.ClientBuffer <= maxWindow
}

// maybeCompact runs the compaction cascade when needed ≥ compactionTriggerPct
// of in.MaxWindow: (1) clear old tool results, (2) summarize with a
// window-aware model, (3) progressive trim. Mutates env in place — caller MUST
// recompute estimates when res.Applied is true. Returns
// ErrContextWindowExceeded if the history overflows even after all tiers;
// no-ops when pct is zero/unset, below threshold, the turn is hard-pinned
// (a client's own compaction turn must not be rewritten, and
// probe/title-gen/classifier turns bypass the scorer), or the harness policy
// defers to the client's own compaction.
func (s *Service) maybeCompact(ctx context.Context, env *translate.RequestEnvelope, in compactionInput) (compactionResult, error) {
	log := observability.FromContext(ctx)
	var res compactionResult
	if s.compactionTriggerPct <= 0 || in.MaxWindow <= 0 || env == nil || s.isHardPinnedTurn(ctx, in.TurnType) {
		return res, nil
	}
	pol := compactionPolicyFor(in.ClientApp)

	needed := func() int { return env.ContextOverflowTokenEstimate() + in.OutputReserve }
	fits := func() bool { return needed() <= in.MaxWindow }
	trigger := int(float64(in.MaxWindow) * s.compactionTriggerPct)
	if needed() < trigger {
		return res, nil
	}
	if fits() && clientWouldCompact(pol, in.RequestedModel, in.MaxWindow) {
		res.DeferredToClient = true
		log.Info("Compaction deferred to client harness",
			"client_app", in.ClientApp,
			"needed", needed(),
			"max_window", in.MaxWindow,
			"client_window", catalog.ContextWindowFor(in.RequestedModel),
		)
		return res, nil
	}
	log.Info("Compaction cascade engaged",
		"client_app", in.ClientApp,
		"needed", needed(),
		"trigger", trigger,
		"max_window", in.MaxWindow,
	)

	// Tier 1: clear stale tool results (cheap, local, no model call).
	if n := env.ClearOldToolResults(pol.ToolResultKeep); n > 0 {
		res.Applied = true
		res.ToolResultsCleared = n
		log.Info("Compaction Tier-1: cleared old tool results", "cleared", n, "needed_after", needed())
	}
	// Tier-1 alone is enough only if it brought the request back under the
	// trigger; merely fitting the window is not — the point of triggering
	// below the window is to summarize while a summarizer can still ingest
	// the history.
	if needed() < trigger {
		res.FinalEstimate = needed()
		return res, nil
	}

	// Tier 3: structured summarization with a window-aware model.
	// Authoritative-policy turns skip LLM summarization; deterministic cleanup and rescue trimming still run.
	if s.compactionSummarizer != nil && !s.authoritativePerTurnSelection(ctx) {
		preferred := ""
		if in.PreferredSummarizer != nil {
			preferred = in.PreferredSummarizer()
		}
		if summary, usage, model, ok := s.runCompactionSummary(ctx, env, preferred, in.Headers); ok {
			// The summary is billed regardless; a rewrite that leaves a
			// fitting request no longer fitting is discarded rather than
			// letting rescue trimming drop context that was already servable.
			fitBefore, before := fits(), env.Clone()
			env.RewriteForCompaction(summary, pol.RecentTurns)
			res.Applied = true
			res.SummaryModel = model
			res.SummaryUsage = usage
			if fitBefore && !fits() {
				*env = *before
				log.Warn("Compaction Tier-3: summary rewrite would overflow; reverted", "summary_model", model, "needed_after", needed())
			} else {
				res.Summarized = true
				log.Info("Compaction Tier-3: history summarized", "summary_model", model, "needed_after", needed())
			}
		}
	}
	if fits() {
		res.FinalEstimate = needed()
		return res, nil
	}

	// Rescue: trim recent turns progressively until the request fits.
	for _, n := range []int{pol.RecentTurns, 6, 3, 1} {
		if env.TrimLastNMessages(n) > 0 {
			res.Applied = true
			res.TrimmedToRecent = n
		}
		if fits() {
			res.FinalEstimate = needed()
			log.Info("Compaction rescue: trimmed to recent turns", "kept_recent", n, "needed_after", needed())
			return res, nil
		}
	}

	// Floor: even the last user turn overflows the largest window.
	res.FinalEstimate = needed()
	return res, fmt.Errorf("context ~%d tokens over largest window %d: %w", res.FinalEstimate, in.MaxWindow, ErrContextWindowExceeded)
}

// emitCompactionSummaryTelemetry records the compaction summary call's
// session-tagged telemetry row (mirrors the switch-handover summary). No-ops
// when the usage carries no tokens.
func (s *Service) emitCompactionSummaryTelemetry(ctx context.Context, requestID, externalID string, usage handover.Usage) {
	s.emitAuxiliaryInferenceTelemetry(ctx, requestID, auxSuffixPrecompactionSummary, externalID, usage)
}

// runCompactionSummary picks a window-aware summarizer model and dispatches the
// structured summary call, honoring the tenant-boundary credential rules used
// by the switch-handover path. Returns ok=false (and logs) when no summarizer
// fits the history, the tenant boundary forbids the call, or the call fails —
// in every such case the caller falls through to trimming.
func (s *Service) runCompactionSummary(ctx context.Context, env *translate.RequestEnvelope, preferred string, reqHeaders http.Header) (string, handover.Usage, string, bool) {
	log := observability.FromContext(ctx)

	model := s.selectCompactionSummarizer(env.ContextOverflowTokenEstimate(), preferred)
	if model == "" {
		log.Info("Compaction Tier-3 skipped: history exceeds every summarizer window", "history", env.ContextOverflowTokenEstimate())
		return "", handover.Usage{}, "", false
	}

	sumProvider := s.compactionSummarizer.Provider()
	sumCreds := resolveSummarizerCreds(ctx, sumProvider, reqHeaders)
	if sumCreds == nil && s.requestUsesNonDeploymentCreds(ctx, reqHeaders) {
		log.Info("Compaction Tier-3 skipped: would cross tenant boundary", "sum_provider", sumProvider)
		return "", handover.Usage{}, "", false
	}
	summCtx := ctx
	if sumCreds != nil {
		summCtx = context.WithValue(ctx, CredentialsContextKey{}, sumCreds)
	} else {
		summCtx = clearCredentials(ctx)
	}

	summary, usage, err := s.compactionSummarizer.SummarizeForCompaction(summCtx, env, model, DefaultCompactionMaxTokens)
	if err != nil {
		log.Warn("Compaction summarizer failed; falling back to trim", "err", err, "model", model)
		return "", handover.Usage{}, "", false
	}
	if summary == "" {
		log.Warn("Compaction summarizer returned empty; falling back to trim", "model", model)
		return "", handover.Usage{}, "", false
	}
	return summary, usage, model, true
}

// compactionHardPin picks the model for a client's own compaction turn: the
// session's active pin when it is mid-tier or better (the model that ran the
// conversation, prompt cache warm), else the configured compaction model.
// ok=false when neither is eligible for this request, so the caller falls
// back to the generic hard-pin tier.
func (s *Service) compactionHardPin(ctx context.Context, sessionKey [sessionpin.SessionKeyLen]byte, role string, req router.Request) (provider, model string, ok bool) {
	if req.EnabledProviders != nil {
		if _, enabled := req.EnabledProviders[providers.ProviderAiand]; !enabled {
			return "", "", false
		}
	}
	eligible := func(m string) bool {
		if !summarizerEligible(m) {
			return false
		}
		if s.availableModels != nil {
			if _, available := s.availableModels[m]; !available {
				return false
			}
		}
		if _, excluded := req.ExcludedModels[m]; excluded {
			return false
		}
		return !automaticallyDisabled(req, m)
	}
	if preferred := s.compactionPreferredSummarizer(ctx, sessionKey, role); eligible(preferred) {
		return providers.ProviderAiand, preferred, true
	}
	if m := s.compactionModelOrDefault(); eligible(m) {
		return providers.ProviderAiand, m, true
	}
	return "", "", false
}
