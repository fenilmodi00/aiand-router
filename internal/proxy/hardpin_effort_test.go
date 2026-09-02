package proxy_test

import (
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"aiand/router/internal/providers"
	"aiand/router/internal/proxy"
	"aiand/router/internal/router"

	"github.com/google/uuid"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"github.com/tidwall/gjson"
)

// anthropicClassifierBody: short max_tokens, no tools, Anthropic surface — the
// shape Claude Code's internal short-form calls produce, which hard-pins.
const anthropicClassifierBody = `{"model":"auto","max_tokens":80,"messages":[{"role":"user","content":"hi how are you"}]}`

// Hard-pinned turns (classifier/probe/title-gen/compaction) are trivially
// short internal calls; they must dispatch at minimal reasoning effort where
// the model's menu allows it. The QA baseline: a greeting on
// deepseek-v4-flash burned ~33 reasoning tokens for "hi how are you"
// (ticket 07).
func TestService_HardPin_ClassifierRunsAtMinimalEffort(t *testing.T) {
	store := newFakePinStore()
	fr := &fakeRouter{decision: router.Decision{Provider: providers.ProviderAiand, Model: "moonshotai/kimi-k3", Reason: "cluster"}}

	okResp := func(w http.ResponseWriter) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_, _ = io.WriteString(w, `{"id":"chatcmpl_1","object":"chat.completion","choices":[{"index":0,"message":{"role":"assistant","content":"ok"},"finish_reason":"stop"}],"usage":{"prompt_tokens":9,"completion_tokens":2}}`)
	}
	aiand := &fakeProvider{proxyResponse: okResp}
	providerMap := map[string]providers.Client{providers.ProviderAiand: aiand}
	svc := proxy.NewService(
		fr, providerMap, nil, false, nil, store, false,
		providers.ProviderAiand, "deepseek-ai/deepseek-v4-flash",
		nil,
	)

	rec := httptest.NewRecorder()
	httpReq := httptest.NewRequest(http.MethodPost, "/v1/messages", strings.NewReader(""))
	require.NoError(t, svc.ProxyMessages(authedCtx(uuid.New().String()), []byte(anthropicClassifierBody), rec, httpReq))

	assert.Equal(t, 0, fr.routeCalls, "Anthropic-source classifier must bypass the cluster scorer")
	assert.Equal(t, "deepseek-ai/deepseek-v4-flash", rec.Header().Get(proxy.HeaderRouterModel),
		"hard-pinned classifier turn must serve the pinned cheap model")
	require.NotEmpty(t, aiand.proxyBodies, "upstream body must have been captured")
	assert.Equal(t, "none", gjson.GetBytes(aiand.proxyBodies[0], "reasoning.effort").String(),
		"flash serves effort 'none'; a hard-pinned greeting must not burn reasoning tokens")
}

// Non-hard-pinned turns on the same model keep the default effort policy: the
// minimal-effort branch is keyed on routeRes.HardPinned, not on the model.
// Uses the OpenAI surface, where short prompts now score (D1 fix).
func TestService_NonHardPinnedTurnKeepsPolicyEffort(t *testing.T) {
	fr := &fakeRouter{decision: router.Decision{Provider: providers.ProviderAiand, Model: "deepseek-ai/deepseek-v4-flash", Reason: "cluster"}}
	okResp := func(w http.ResponseWriter) {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_, _ = io.WriteString(w, `{"id":"chatcmpl_1","object":"chat.completion","choices":[{"index":0,"message":{"role":"assistant","content":"ok"},"finish_reason":"stop"}],"usage":{"prompt_tokens":9,"completion_tokens":2}}`)
	}
	aiand := &fakeProvider{proxyResponse: okResp}
	providerMap := map[string]providers.Client{providers.ProviderAiand: aiand}
	svc := proxy.NewService(
		fr, providerMap, nil, false, nil, newFakePinStore(), false,
		providers.ProviderAiand, "deepseek-ai/deepseek-v4-flash",
		nil,
	)

	// The QA matrix shape on the OpenAI surface: post-D1 this classifies
	// MainLoop and reaches the scorer instead of hard-pinning.
	body := `{"model":"auto","max_tokens":80,"messages":[{"role":"user","content":"hi how are you"}]}`
	rec := httptest.NewRecorder()
	httpReq := httptest.NewRequest(http.MethodPost, "/v1/chat/completions", strings.NewReader(""))
	require.NoError(t, svc.ProxyOpenAIChatCompletion(authedCtx(uuid.New().String()), []byte(body), rec, httpReq))

	assert.Equal(t, 1, fr.routeCalls, "OpenAI-source short prompt must reach the scorer (ticket 04 fix)")
	require.NotEmpty(t, aiand.proxyBodies)
	assert.Equal(t, "", gjson.GetBytes(aiand.proxyBodies[0], "reasoning_effort").String(),
		"scored flash turns keep the default (no policy effort) — minimal effort is hard-pin-only")
}
