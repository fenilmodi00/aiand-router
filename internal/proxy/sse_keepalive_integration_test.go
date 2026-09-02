package proxy_test

import (
	"context"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"aiand/router/internal/providers"
	"aiand/router/internal/providers/openaicompat"
	"aiand/router/internal/proxy"
	"aiand/router/internal/router"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// TestProxyMessages_KeepaliveDuringUpstreamSilence verifies a committed stream
// silent during reasoning is padded so the client byte watchdog doesn't abort it.
func TestProxyMessages_KeepaliveDuringUpstreamSilence(t *testing.T) {
	const upstreamSilence = 250 * time.Millisecond

	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/event-stream")
		w.WriteHeader(http.StatusOK)
		flusher, _ := w.(http.Flusher)
		write := func(chunk string) {
			_, _ = w.Write([]byte(chunk))
			if flusher != nil {
				flusher.Flush()
			}
		}

		// The ai&-only promotion dispatches this turn onto /v1/responses, so
		// the stall fixture speaks Responses SSE around the silent window.
		write(`data: {"type":"response.created","response":{"id":"resp_ka","status":"in_progress"}}` + "\n\n")
		write(`data: {"type":"response.output_text.delta","output_index":0,"delta":"thinking"}` + "\n\n")
		// The stall: committed, then nothing the translator can forward.
		time.Sleep(upstreamSilence)
		write(`data: {"type":"response.output_text.delta","output_index":0,"delta":" done"}` + "\n\n")
		write(`data: {"type":"response.completed","response":{"id":"resp_ka","status":"completed","output":[{"type":"message","role":"assistant","content":[{"type":"output_text","text":"thinking done"}]}],"usage":{"input_tokens":5,"output_tokens":2}}}` + "\n\n")
	}))
	defer upstream.Close()

	svc := proxy.NewService(
		&fakeRouter{decision: router.Decision{Provider: providers.ProviderAiand, Model: "deepseek-ai/deepseek-v4-pro"}},
		map[string]providers.Client{providers.ProviderAiand: openaicompat.NewClient("test-fw-key", upstream.URL)},
		nil, false, nil, nil, false, providers.ProviderAiand, "deepseek-ai/deepseek-v4-flash", nil,
	).WithDeploymentKeyedProviders(map[string]struct{}{providers.ProviderAiand: {}}).
		WithSSEKeepalive(40 * time.Millisecond)

	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/v1/messages", strings.NewReader(""))
	body := []byte(`{"model":"deepseek-ai/deepseek-v4-pro","stream":true,"messages":[{"role":"user","content":"hi"}]}`)

	require.NoError(t, svc.ProxyMessages(context.Background(), body, rec, req))

	got := rec.Body.String()
	assert.GreaterOrEqual(t, strings.Count(got, "event: ping"), 2,
		"a stalled-but-live stream must be padded with pings")

	// The padding must not break the turn: real frames still bracket the stream,
	// the answer survives, and no ping precedes message_start.
	assert.Contains(t, got, "event: message_start")
	assert.Contains(t, got, "event: message_stop")
	assert.Contains(t, got, "thinking")
	assert.Contains(t, got, " done")
	assert.Less(t, strings.Index(got, "event: message_start"), strings.Index(got, "event: ping"),
		"keepalives must never precede the stream envelope")
}

// The keepalive is a kill-switchable addition: with it off, the stream is
// byte-for-byte what it was before, so an operator can always turn it back off.
func TestProxyMessages_KeepaliveDisabledLeavesStreamUnpadded(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/event-stream")
		w.WriteHeader(http.StatusOK)
		flusher, _ := w.(http.Flusher)
		write := func(chunk string) {
			_, _ = w.Write([]byte(chunk))
			if flusher != nil {
				flusher.Flush()
			}
		}
		write(`data: {"type":"response.created","response":{"id":"resp_ka2","status":"in_progress"}}` + "\n\n")
		write(`data: {"type":"response.output_text.delta","output_index":0,"delta":"hi"}` + "\n\n")
		time.Sleep(150 * time.Millisecond)
		write(`data: {"type":"response.completed","response":{"id":"resp_ka2","status":"completed","output":[{"type":"message","role":"assistant","content":[{"type":"output_text","text":"hi"}]}],"usage":{"input_tokens":5,"output_tokens":1}}}` + "\n\n")
	}))
	defer upstream.Close()
}

// TestProxyOpenAIChatCompletion_KeepaliveDuringUpstreamSilence mirrors the
// ProxyMessages keepalive test for the OpenAI chat surface: a committed
// chat/completions stream silent during reasoning must be padded with the
// OpenAI-legal SSE comment frame.
func TestProxyOpenAIChatCompletion_KeepaliveDuringUpstreamSilence(t *testing.T) {
	const upstreamSilence = 250 * time.Millisecond

	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/event-stream")
		w.WriteHeader(http.StatusOK)
		flusher, _ := w.(http.Flusher)
		write := func(chunk string) {
			_, _ = w.Write([]byte(chunk))
			if flusher != nil {
				flusher.Flush()
			}
		}

		// The chat caller is dispatched onto /v1/responses, so the stall
		// fixture speaks Responses SSE around the silent window.
		write(`data: {"type":"response.created","response":{"id":"resp_oai","status":"in_progress"}}` + "\n\n")
		write(`data: {"type":"response.output_text.delta","output_index":0,"delta":"thinking"}` + "\n\n")
		// The stall: committed, then nothing the translator can forward.
		time.Sleep(upstreamSilence)
		write(`data: {"type":"response.output_text.delta","output_index":0,"delta":" done"}` + "\n\n")
		write(`data: {"type":"response.completed","response":{"id":"resp_oai","status":"completed","output":[{"type":"message","role":"assistant","content":[{"type":"output_text","text":"thinking done"}]}],"usage":{"input_tokens":5,"output_tokens":2}}}` + "\n\n")
	}))
	defer upstream.Close()

	svc := proxy.NewService(
		&fakeRouter{decision: router.Decision{Provider: providers.ProviderAiand, Model: "deepseek-ai/deepseek-v4-pro"}},
		map[string]providers.Client{providers.ProviderAiand: openaicompat.NewClient("test-fw-key", upstream.URL)},
		nil, false, nil, nil, false, providers.ProviderAiand, "deepseek-ai/deepseek-v4-flash", nil,
	).WithDeploymentKeyedProviders(map[string]struct{}{providers.ProviderAiand: {}}).
		WithSSEKeepalive(40 * time.Millisecond)

	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/v1/chat/completions", strings.NewReader(""))
	body := []byte(`{"model":"deepseek-ai/deepseek-v4-pro","stream":true,"messages":[{"role":"user","content":"hi"}]}`)

	require.NoError(t, svc.ProxyOpenAIChatCompletion(context.Background(), body, rec, req))

	got := rec.Body.String()
	assert.GreaterOrEqual(t, strings.Count(got, ": keepalive"), 2,
		"a stalled-but-live stream must be padded with comment frames")

	// The padding must not break the turn: real chat chunks still bracket the
	// stream, the answer survives, and no keepalive precedes the first chunk.
	assert.Contains(t, got, `"object":"chat.completion.chunk"`)
	assert.Contains(t, got, `"content":"thinking"`)
	assert.Contains(t, got, `"content":" done"`)
	assert.Contains(t, got, "data: [DONE]")
	assert.Less(t, strings.Index(got, `"object":"chat.completion.chunk"`), strings.Index(got, ": keepalive"),
		"keepalives must never precede the stream envelope")
}

// A prompt upstream leaves no silence window, so no keepalive frame may
// appear even with the keepalive interval armed.
func TestProxyOpenAIChatCompletion_KeepaliveAbsentOnPromptUpstream(t *testing.T) {
	upstream := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "text/event-stream")
		w.WriteHeader(http.StatusOK)
		for _, frame := range []string{
			`{"type":"response.created","response":{"id":"resp_oai2","status":"in_progress"}}`,
			`{"type":"response.output_text.delta","output_index":0,"delta":"hi"}`,
			`{"type":"response.completed","response":{"id":"resp_oai2","status":"completed","output":[{"type":"message","role":"assistant","content":[{"type":"output_text","text":"hi"}]}],"usage":{"input_tokens":5,"output_tokens":1}}}`,
		} {
			_, _ = io.WriteString(w, "data: "+frame+"\n\n")
		}
	}))
	defer upstream.Close()

	svc := proxy.NewService(
		&fakeRouter{decision: router.Decision{Provider: providers.ProviderAiand, Model: "deepseek-ai/deepseek-v4-pro"}},
		map[string]providers.Client{providers.ProviderAiand: openaicompat.NewClient("test-fw-key", upstream.URL)},
		nil, false, nil, nil, false, providers.ProviderAiand, "deepseek-ai/deepseek-v4-flash", nil,
	).WithDeploymentKeyedProviders(map[string]struct{}{providers.ProviderAiand: {}}).
		WithSSEKeepalive(40 * time.Millisecond)

	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/v1/chat/completions", strings.NewReader(""))
	body := []byte(`{"model":"deepseek-ai/deepseek-v4-pro","stream":true,"messages":[{"role":"user","content":"hi"}]}`)

	require.NoError(t, svc.ProxyOpenAIChatCompletion(context.Background(), body, rec, req))

	assert.NotContains(t, rec.Body.String(), ": keepalive",
		"a prompt upstream must receive no keepalive padding")
}
