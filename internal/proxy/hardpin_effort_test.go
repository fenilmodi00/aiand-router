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

// Scored easy-tier MainLoop turns dispatch at minimal reasoning effort (GH #15):
// trivial prompts the scorer routes to the cheap tier (flash/qwen) must not
// burn reasoning tokens. Keyed on tier + turn type, so hardest-tier behavior
// and non-main turns are untouched.
func TestService_ScoredEasyTierMainLoopRunsAtMinimalEffort(t *testing.T) {
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

	// The QA matrix shape on the OpenAI surface: classifies MainLoop and
	// reaches the scorer (D1 fix), which routes the greeting to flash.
	body := `{"model":"auto","max_tokens":80,"messages":[{"role":"user","content":"hi how are you"}]}`
	rec := httptest.NewRecorder()
	httpReq := httptest.NewRequest(http.MethodPost, "/v1/chat/completions", strings.NewReader(""))
	require.NoError(t, svc.ProxyOpenAIChatCompletion(authedCtx(uuid.New().String()), []byte(body), rec, httpReq))

	assert.Equal(t, 1, fr.routeCalls, "OpenAI-source short prompt must reach the scorer (ticket 04 fix)")
	require.NotEmpty(t, aiand.proxyBodies)
	assert.Equal(t, "none", gjson.GetBytes(aiand.proxyBodies[0], "reasoning.effort").String(),
		"scored easy-tier MainLoop turns serve effort 'none' (GH #15); the chat surface dispatches flash via /v1/responses")
}

// The Anthropic surface gets the same easy-tier minimal-effort policy on its
// scored MainLoop turns (reasoning.effort on the translated wire).
func TestService_ScoredEasyTierMainLoopRunsAtMinimalEffort_AnthropicSurface(t *testing.T) {
	fr := &fakeRouter{decision: router.Decision{Provider: providers.ProviderAiand, Model: "qwen/qwen3.8-27b", Reason: "cluster"}}
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

	// Tools + high max_tokens: a main-loop turn the classifier/probe gates
	// can't catch, so it scores and the router picks the easy-tier model.
	body := `{"model":"auto","max_tokens":8192,"tools":[{"type":"function","function":{"name":"read_file","parameters":{"type":"object"}}}],"messages":[{"role":"user","content":"summarize /tmp/notes.txt"}]}`
	rec := httptest.NewRecorder()
	httpReq := httptest.NewRequest(http.MethodPost, "/v1/messages", strings.NewReader(""))
	require.NoError(t, svc.ProxyMessages(authedCtx(uuid.New().String()), []byte(body), rec, httpReq))

	require.NotEmpty(t, aiand.proxyBodies)
	assert.Equal(t, "none", gjson.GetBytes(aiand.proxyBodies[0], "reasoning.effort").String(),
		"scored easy-tier MainLoop turns serve effort 'none' on the translated wire (GH #15)")
}

// Hardest-tier scored turns keep the default effort policy: the minimal-effort
// branch is keyed on tier, not on scored-ness.
func TestService_ScoredHardTierTurnKeepsPolicyEffort(t *testing.T) {
	fr := &fakeRouter{decision: router.Decision{Provider: providers.ProviderAiand, Model: "moonshotai/kimi-k3", Reason: "cluster"}}
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

	body := `{"model":"auto","max_tokens":8192,"messages":[{"role":"user","content":"refactor the parser to handle nested generics"}]}`
	rec := httptest.NewRecorder()
	httpReq := httptest.NewRequest(http.MethodPost, "/v1/chat/completions", strings.NewReader(""))
	require.NoError(t, svc.ProxyOpenAIChatCompletion(authedCtx(uuid.New().String()), []byte(body), rec, httpReq))

	require.NotEmpty(t, aiand.proxyBodies)
	assert.Equal(t, "", gjson.GetBytes(aiand.proxyBodies[0], "reasoning_effort").String(),
		"hardest-tier scored turns keep the default (no policy effort) — minimal effort is easy-tier-only (GH #15)")
}
