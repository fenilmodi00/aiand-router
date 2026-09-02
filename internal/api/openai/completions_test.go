package openai_test

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	openaiapi "aiand/router/internal/api/openai"
	"aiand/router/internal/providers"
	"aiand/router/internal/proxy"
	"aiand/router/internal/router"
	"aiand/router/internal/router/cluster"

	"github.com/gin-gonic/gin"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// fakeRouter lets tests control exactly what routing decision (or error) the
// proxy.Service's scorer step returns, without needing a real cluster router.
type fakeRouter struct {
	decision router.Decision
	err      error
}

func (f *fakeRouter) Route(context.Context, router.Request) (router.Decision, error) {
	return f.decision, f.err
}

// fakeProviderClient is a minimal providers.Client double: Proxy returns
// whatever the test wants, optionally writing a response first.
type fakeProviderClient struct {
	proxyErr    error
	proxyStatus int
	proxyBody   string
}

func (f *fakeProviderClient) Proxy(_ context.Context, _ router.Decision, _ providers.PreparedRequest, w http.ResponseWriter, _ *http.Request) error {
	if f.proxyErr != nil {
		if f.proxyStatus != 0 {
			w.WriteHeader(f.proxyStatus)
		}
		if f.proxyBody != "" {
			_, _ = w.Write([]byte(f.proxyBody))
		}
		return f.proxyErr
	}
	status := f.proxyStatus
	if status == 0 {
		status = http.StatusOK
	}
	w.WriteHeader(status)
	_, _ = w.Write([]byte(f.proxyBody))
	return nil
}

func (f *fakeProviderClient) Passthrough(_ context.Context, _ providers.PreparedRequest, w http.ResponseWriter, _ *http.Request) error {
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write([]byte(f.proxyBody))
	return nil
}

// newTestService wires a proxy.Service with a fake router and optional fake
// provider, no real I/O.
func newTestService(r router.Router, clientName string, client providers.Client) *proxy.Service {
	providerMap := map[string]providers.Client{}
	if clientName != "" && client != nil {
		providerMap[clientName] = client
	}
	return proxy.NewService(r, providerMap, nil, false, nil, nil, false, "", "", nil)
}

func errorEnvelope(t *testing.T, body []byte) map[string]any {
	t.Helper()
	var got map[string]any
	require.NoError(t, json.Unmarshal(body, &got))
	errObj, ok := got["error"].(map[string]any)
	require.True(t, ok, "expected error envelope to carry an \"error\" object")
	return errObj
}

func engine(svc *proxy.Service) *gin.Engine {
	gin.SetMode(gin.TestMode)
	e := gin.New()
	e.POST("/v1/chat/completions", openaiapi.ChatCompletionHandler(svc, nil))
	e.POST("/v1/responses", openaiapi.ResponsesHandler(svc, nil))
	return e
}

func post(engine *gin.Engine, path string, body []byte) *httptest.ResponseRecorder {
	rec := httptest.NewRecorder()
	engine.ServeHTTP(rec, httptest.NewRequest(http.MethodPost, path, bytes.NewReader(body)))
	return rec
}

// max_tokens > 256 so DetectFromEnvelope treats this as a MainLoop turn, not
// a probe/classifier.
const validChatBody = `{"model":"auto","messages":[{"role":"user","content":"hi"}],"max_tokens":4096}`

func TestChatCompletionHandler_MissingMessagesReturns400(t *testing.T) {
	svc := newTestService(&fakeRouter{}, "", nil)
	rec := post(engine(svc), "/v1/chat/completions", []byte(`{"model":"auto","max_tokens":4096}`))

	require.Equal(t, http.StatusBadRequest, rec.Code)
	errObj := errorEnvelope(t, rec.Body.Bytes())
	assert.Equal(t, "invalid_request_error", errObj["type"])
	assert.Contains(t, errObj["message"], "messages")
}

func TestChatCompletionHandler_EmptyMessagesReturns400(t *testing.T) {
	svc := newTestService(&fakeRouter{}, "", nil)
	rec := post(engine(svc), "/v1/chat/completions", []byte(`{"model":"auto","messages":[],"max_tokens":4096}`))

	require.Equal(t, http.StatusBadRequest, rec.Code)
	errObj := errorEnvelope(t, rec.Body.Bytes())
	assert.Equal(t, "invalid_request_error", errObj["type"])
	assert.Contains(t, errObj["message"], "messages")
}

func TestChatCompletionHandler_NegativeMaxTokensReturns400(t *testing.T) {
	svc := newTestService(&fakeRouter{}, "", nil)
	rec := post(engine(svc), "/v1/chat/completions", []byte(`{"model":"auto","messages":[{"role":"user","content":"hi"}],"max_tokens":-5}`))

	require.Equal(t, http.StatusBadRequest, rec.Code)
	errObj := errorEnvelope(t, rec.Body.Bytes())
	assert.Equal(t, "invalid_request_error", errObj["type"])
	assert.Contains(t, errObj["message"], "max_tokens")
}

func TestChatCompletionHandler_StringMaxTokensReturns400(t *testing.T) {
	svc := newTestService(&fakeRouter{}, "", nil)
	rec := post(engine(svc), "/v1/chat/completions", []byte(`{"model":"auto","messages":[{"role":"user","content":"hi"}],"max_tokens":"eighty"}`))

	require.Equal(t, http.StatusBadRequest, rec.Code)
	errObj := errorEnvelope(t, rec.Body.Bytes())
	assert.Equal(t, "invalid_request_error", errObj["type"])
	assert.Contains(t, errObj["message"], "max_tokens")
}

func TestChatCompletionHandler_NegativeMaxCompletionTokensReturns400(t *testing.T) {
	svc := newTestService(&fakeRouter{}, "", nil)
	rec := post(engine(svc), "/v1/chat/completions", []byte(`{"model":"auto","messages":[{"role":"user","content":"hi"}],"max_completion_tokens":-1}`))

	require.Equal(t, http.StatusBadRequest, rec.Code)
	errObj := errorEnvelope(t, rec.Body.Bytes())
	assert.Contains(t, errObj["message"], "max_completion_tokens")
}

func TestChatCompletionHandler_NegativeMaxOutputTokensOnResponsesReturns400(t *testing.T) {
	svc := newTestService(&fakeRouter{}, "", nil)
	rec := post(engine(svc), "/v1/responses", []byte(`{"model":"auto","input":"hi","max_output_tokens":-1}`))

	require.Equal(t, http.StatusBadRequest, rec.Code)
	errObj := errorEnvelope(t, rec.Body.Bytes())
	assert.Contains(t, errObj["message"], "max_output_tokens")
}

// A valid body must still reach the proxy — the validation gate never
// short-circuits well-formed requests.
func TestChatCompletionHandler_ValidBodyReachesProxy(t *testing.T) {
	client := &fakeProviderClient{proxyStatus: http.StatusOK, proxyBody: "data: {\"type\":\"response.created\",\"response\":{\"id\":\"resp_1\",\"status\":\"in_progress\"}}\n\ndata: {\"type\":\"response.output_text.delta\",\"output_index\":0,\"delta\":\"ok\"}\n\ndata: {\"type\":\"response.completed\",\"response\":{\"id\":\"resp_1\",\"status\":\"completed\",\"output\":[{\"type\":\"message\",\"role\":\"assistant\",\"content\":[{\"type\":\"output_text\",\"text\":\"ok\"}]}],\"usage\":{\"input_tokens\":1,\"output_tokens\":1}}}\n\n"}
	svc := newTestService(
		&fakeRouter{decision: router.Decision{Provider: providers.ProviderAiand, Model: "claude-sonnet-4-5"}},
		providers.ProviderAiand, client,
	)

	rec := post(engine(svc), "/v1/chat/completions", []byte(validChatBody))

	require.Equal(t, http.StatusOK, rec.Code)
	assert.Equal(t, "claude-sonnet-4-5", rec.Header().Get("x-router-model"))
}

// Genuine scorer failure must still fail closed with 503 on a valid body.
func TestChatCompletionHandler_ClusterUnavailableReturns503(t *testing.T) {
	svc := newTestService(&fakeRouter{err: cluster.ErrClusterUnavailable}, "", nil)

	rec := post(engine(svc), "/v1/chat/completions", []byte(validChatBody))

	require.Equal(t, http.StatusServiceUnavailable, rec.Code)
	assert.Equal(t, "1", rec.Header().Get("Retry-After"))
	errObj := errorEnvelope(t, rec.Body.Bytes())
	assert.Equal(t, "api_error", errObj["type"])
}

func TestChatCompletionHandler_NonJSONObjectBodyReturns400(t *testing.T) {
	svc := newTestService(&fakeRouter{}, "", nil)
	rec := post(engine(svc), "/v1/chat/completions", []byte(`[]`))

	require.Equal(t, http.StatusBadRequest, rec.Code)
	errObj := errorEnvelope(t, rec.Body.Bytes())
	assert.Equal(t, "invalid_request_error", errObj["type"])
}

// The Responses surface: a valid input body reaches the proxy too. The model
// must be one the unknown-model policy accepts (catalog id), so this
// exercises the dispatch path, not the 400 rejection.
func TestResponsesHandler_ValidBodyReachesProxy(t *testing.T) {
	client := &fakeProviderClient{proxyStatus: http.StatusOK, proxyBody: "data: {\"type\":\"response.created\",\"response\":{\"id\":\"resp_1\",\"status\":\"in_progress\"}}\n\ndata: {\"type\":\"response.output_text.delta\",\"output_index\":0,\"delta\":\"ok\"}\n\ndata: {\"type\":\"response.completed\",\"response\":{\"id\":\"resp_1\",\"status\":\"completed\",\"output\":[{\"type\":\"message\",\"role\":\"assistant\",\"content\":[{\"type\":\"output_text\",\"text\":\"ok\"}]}],\"usage\":{\"input_tokens\":1,\"output_tokens\":1}}}\n\n"}
	svc := newTestService(
		&fakeRouter{decision: router.Decision{Provider: providers.ProviderAiand, Model: "zai-org/glm-5.3"}},
		providers.ProviderAiand, client,
	)

	rec := post(engine(svc), "/v1/responses", []byte(`{"model":"zai-org/glm-5.3","input":"hi","max_output_tokens":4096}`))

	require.Equal(t, http.StatusOK, rec.Code)
	assert.Equal(t, "zai-org/glm-5.3", rec.Header().Get("x-router-model"))
}
