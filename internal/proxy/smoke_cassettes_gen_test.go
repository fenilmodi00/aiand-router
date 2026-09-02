//go:build gencassettes

package proxy_test

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"aiand/router/internal/providers"
	"aiand/router/internal/proxy"
	"aiand/router/internal/router"
	"aiand/router/internal/router/cache"
	"aiand/router/internal/translate"

	"github.com/google/uuid"
	"github.com/stretchr/testify/require"
	"github.com/tidwall/gjson"
	"github.com/tidwall/sjson"
)

const (
	smokePinModel   = "deepseek-ai/deepseek-v4-flash"
	cassettesDirRel = "../../smoke/mitmproxy/cassettes"
)

type smokeUsageSpec struct {
	input, output, cached, cacheWrite int
}

// TestGenerateSmokeCassettes rebuilds smoke MITM cassettes for POST /v1/responses
// after upstream dispatch moved off native Anthropic /v1/messages. Run:
//
//	go test -tags gencassettes ./internal/proxy -run TestGenerateSmokeCassettes -count=1
func TestGenerateSmokeCassettes(t *testing.T) {
	systemPrompt := loadSmokeSystemPrompt(t)

	type scenario struct {
		name      string
		build     func() []byte
		pinModel  string
		cluster   bool
		stream    bool
		usage     smokeUsageSpec
		toolCall  bool
		replyText string
	}

	scenarios := []scenario{
		{
			name: "basic-nonstream-ok",
			build: func() []byte {
				return smokeBody(t, systemPrompt, smokeOpts{
					userID: "smoke-basic-nonstream", maxTokens: 64,
					text: "Reply with exactly the word: ok",
				})
			},
			pinModel: smokePinModel,
			usage:    smokeUsageSpec{input: 120, output: 2},
		},
		{
			name: "basic-stream-ok",
			build: func() []byte {
				return smokeBody(t, systemPrompt, smokeOpts{
					userID: "smoke-basic-stream", maxTokens: 64, stream: true,
					text: "Reply with exactly the word: ok",
				})
			},
			pinModel: smokePinModel,
			stream:   true,
			usage:    smokeUsageSpec{input: 120, output: 2},
		},
		{
			name: "stream-bash-tool",
			build: func() []byte {
				return smokeBody(t, systemPrompt, smokeOpts{
					userID: "smoke-stream-lifecycle", maxTokens: 256, stream: true,
					text: "Use the Bash tool to list files in the current directory. Call the tool; do not answer in prose.",
				})
			},
			pinModel: smokePinModel,
			stream:   true,
			toolCall: true,
			usage:     smokeUsageSpec{input: 140, output: 24},
		},
		{
			name: "semantic-parity",
			build: func() []byte {
				return smokeBody(t, systemPrompt, smokeOpts{
					userID: "smoke-semantic-cache", maxTokens: 256,
					text: "Reply with exactly the word: parity. Do not use tools.",
				})
			},
			pinModel: smokePinModel,
			usage:     smokeUsageSpec{input: 130, output: 1},
			replyText: "parity",
		},
		{
			name: "semantic-stream",
			build: func() []byte {
				return smokeBody(t, systemPrompt, smokeOpts{
					userID: "smoke-semantic-cache-stream", maxTokens: 256, stream: true,
					text: "Reply with exactly the word: stream. Do not use tools.",
				})
			},
			pinModel:  smokePinModel,
			stream:    true,
			usage:     smokeUsageSpec{input: 130, output: 1},
			replyText: "stream",
		},
		{
			name: "cache-say-one",
			build: func() []byte {
				return smokeBody(t, systemPrompt, smokeOpts{
					userID: "smoke-cache-injected", maxTokens: 32, text: "Say: one",
				})
			},
			pinModel: smokePinModel,
			usage:    smokeUsageSpec{input: 9000, output: 2, cacheWrite: 8000},
		},
		{
			name: "cache-say-two",
			build: func() []byte {
				return smokeBody(t, systemPrompt, smokeOpts{
					userID: "smoke-cache-injected", maxTokens: 32, text: "Say: two",
				})
			},
			pinModel: smokePinModel,
			usage:    smokeUsageSpec{input: 120, output: 2, cached: 8000},
		},
		{
			name: "cache-at-capacity",
			build: func() []byte {
				return smokeBody(t, systemPrompt, smokeOpts{
					userID: "smoke-cache-capacity", maxTokens: 32,
					cachedTools: 2, toolCache: "5m", sysCache: "5m", text: "Say: ok",
				})
			},
			pinModel: smokePinModel,
			usage:    smokeUsageSpec{input: 9000, output: 2, cacheWrite: 7000},
		},
		{
			name: "cache-ttl-alpha",
			build: func() []byte {
				return smokeBody(t, systemPrompt, smokeOpts{
					userID: "smoke-cache-ttl-order", maxTokens: 32,
					msgCache: "1h", text: "Say: alpha",
				})
			},
			pinModel: smokePinModel,
			usage:    smokeUsageSpec{input: 9000, output: 2, cacheWrite: 8000},
		},
		{
			name: "cache-ttl-beta",
			build: func() []byte {
				return smokeBody(t, systemPrompt, smokeOpts{
					userID: "smoke-cache-ttl-order", maxTokens: 32,
					msgCache: "1h", text: "Say: beta",
				})
			},
			pinModel: smokePinModel,
			usage:    smokeUsageSpec{input: 120, output: 2, cached: 8000},
		},
		{
			name: "openai-typeless-tool",
			build: func() []byte {
				return smokeBody(t, systemPrompt, smokeOpts{
					userID: "smoke-openai-typeless-arg", maxTokens: 64,
					text: "Reply with exactly the word: ok. Do not call any tool.",
					customTools: []map[string]any{smokeTool("Workflow", "Execute a workflow script", map[string]any{
						"scriptPath": map[string]any{"type": "string", "description": "Path to a workflow script file"},
						"args":       map[string]any{"description": "Optional input value, verbatim — any JSON value, no fixed shape"},
					})},
				})
			},
			pinModel: smokePinModel,
			usage:    smokeUsageSpec{input: 130, output: 2},
		},
		{
			name: "model-auto-cluster",
			build: func() []byte {
				body := smokeBody(t, systemPrompt, smokeOpts{
					userID: "smoke-basic-nonstream", maxTokens: 64,
					text: "Reply with exactly the word: ok",
				})
				out, err := sjson.SetBytes(body, "model", "auto")
				require.NoError(t, err)
				return out
			},
			// Cluster v0.78 lands on motif-3 for this fixture; pin the router
			// decision so the emitted upstream body matches replay-only CI.
			cluster: true,
			usage:   smokeUsageSpec{input: 120, output: 2},
		},
	}

	dir := filepath.Clean(filepath.Join(".", cassettesDirRel))
	require.NoError(t, os.MkdirAll(dir, 0o755))

	seen := map[string]string{}
	for _, sc := range scenarios {
		sc := sc
		t.Run(sc.name, func(t *testing.T) {
			body := sc.build
			if sc.pinModel != "" {
				orig := sc.build()
				body = func() []byte { return applySmokeModelField(orig, sc.pinModel) }
			}
			provider := &fakeProvider{}
			var svc *proxy.Service
			if sc.cluster {
				svc = smokeService(&fakeRouter{
					decision: router.Decision{
						Provider: providers.ProviderAiand,
						Model:    "motif-technologies/motif-3",
						Reason:   "cluster:v0.78 top_p=[2,4,9,11] model=motif-technologies/motif-3 provider=aiand",
						Metadata: &router.RoutingMetadata{
							Embedding:  embeddingFixture(7),
							ClusterIDs: []int{2, 4, 9, 11},
						},
					},
				}, provider)
			} else {
				svc = smokeService(&fakeRouter{
					decision: router.Decision{
						Provider: providers.ProviderAiand,
						Model:    smokePinModel,
						Reason:   translate.ReasonUserForceModel,
						Metadata: &router.RoutingMetadata{
							Embedding:  embeddingFixture(7),
							ClusterIDs: []int{2, 4, 9, 11},
						},
					},
				}, provider)
			}

			reply := sc.replyText
			if reply == "" {
				reply = "ok"
			}
			upstreamModel := smokePinModel
			if sc.cluster {
				upstreamModel = "motif-technologies/motif-3"
			}
			// Responses upstream always streams SSE, even when the Anthropic client
			// asked for a buffered turn (see conformance_test.go).
			provider.proxyResponse = func(w http.ResponseWriter) {
				w.Header().Set("Content-Type", "text/event-stream; charset=utf-8")
				_, _ = w.Write([]byte(buildResponsesStream(sc.usage, sc.toolCall, upstreamModel, reply)))
			}

			rec := httptest.NewRecorder()
			reqBody := body()
			req := httptest.NewRequest(http.MethodPost, "/v1/messages", bytes.NewReader(reqBody))
			ctx := authedCtx(uuid.New().String())
			require.NoError(t, svc.ProxyMessages(ctx, reqBody, rec, req))
			require.Equal(t, http.StatusOK, rec.Code, "proxy: %s", rec.Body.String())
			require.Len(t, provider.proxyBodies, 1)
			require.Equal(t, providers.EndpointResponses, provider.proxyEndpoints[0])

			upstream := provider.proxyBodies[0]
			key := smokeRequestKey(http.MethodPost, "/v1/responses", upstream)
			if prev, ok := seen[key]; ok {
				if prev != sc.name {
					t.Logf("sharing cassette key %s (%s reuses %s upstream body)", key, sc.name, prev)
				}
				return
			}
			seen[key] = sc.name

			routedModel := gjson.GetBytes(upstream, "model").String()
			if routedModel == "" {
				routedModel = smokePinModel
			}
			respBody := []byte(buildResponsesStream(sc.usage, sc.toolCall, routedModel, reply))
			c := smokeCassette{
				Method:     http.MethodPost,
				Path:       "/v1/responses",
				StatusCode: http.StatusOK,
				Headers:    map[string]string{"Content-Type": "text/event-stream; charset=utf-8"},
				Body:       string(respBody),
			}
			path := filepath.Join(dir, key+".json")
			data, err := json.MarshalIndent(c, "", "  ")
			require.NoError(t, err)
			require.NoError(t, os.WriteFile(path, append(data, '\n'), 0o644))
			t.Logf("wrote %s (%s)", path, sc.name)
		})
	}

	// Retire stale native Anthropic cassettes — replay keys on /v1/responses now.
	for _, ent := range []string{
		"0feb08ea0fc4a2ac2adefd797e470df5d06abdf412672c2423be4c9a696e067a.json",
		"2ad7397c4dc74d96a7206c34493417fac93676705efd719ba4a754ffffef4a60.json",
		"53b462972e28354dc4af2e11bc384ed32264a03dfa74391358671f9f63529fa1.json",
		"7fbc7a63fae278692c893ba8e341f5b0074ef0130266b2cdb7ab00b59b61e2bf.json",
		"9b626717e3f2dc5919d7a7f1eb5e942a0986c13507477a7408990384faa33e5a.json",
		"ce7b8426d863183f7eb03e632a3dace137bed9fbb8ce04b7734af34dabb33d19.json",
		"d6fc9046ebb4ec512f2ed0e9faacbcfb1d3a0c8a4f7d49c28a526dccd6ffc302.json",
		"f3249ba5e36d05b18079f731c9bab5156c2bbb148180e01e466ef57c685fd298.json",
	} {
		_ = os.Remove(filepath.Join(dir, ent))
	}
}

type smokeCassette struct {
	Method     string            `json:"method"`
	Path       string            `json:"path"`
	StatusCode int               `json:"status_code"`
	Headers    map[string]string `json:"headers"`
	Body       string            `json:"body"`
}

type smokeOpts struct {
	userID      string
	maxTokens   int
	stream      bool
	text        string
	sysCache    string
	msgCache    string
	toolCache   string
	cachedTools int
	customTools []map[string]any
}

func loadSmokeSystemPrompt(t *testing.T) string {
	t.Helper()
	data, err := os.ReadFile(filepath.Join("..", "..", "smoke", "fixtures", "system_prompt.txt"))
	require.NoError(t, err)
	return string(data)
}

func smokeService(r router.Router, provider *fakeProvider) *proxy.Service {
	return proxy.NewService(
		r,
		map[string]providers.Client{providers.ProviderAiand: provider},
		nil, false, cache.New(cache.DefaultConfig()), nil, false,
		providers.ProviderAiand, "deepseek-ai/deepseek-v4-pro", nil,
	).WithDeploymentKeyedProviders(map[string]struct{}{providers.ProviderAiand: {}}).
		WithAvailableModels(map[string]struct{}{
			smokePinModel:                  {},
			"motif-technologies/motif-3":   {},
			"moonshotai/kimi-k3":           {},
			"qwen/qwen3.8-27b":             {},
			"deepseek-ai/deepseek-v4-pro":  {},
		})
}

func smokeBody(t *testing.T, systemPrompt string, o smokeOpts) []byte {
	t.Helper()
	if o.maxTokens == 0 {
		o.maxTokens = 4096
	}
	sysBlock := map[string]any{"type": "text", "text": systemPrompt}
	if o.sysCache != "" {
		sysBlock["cache_control"] = smokeCacheControl(o.sysCache)
	}
	userBlock := map[string]any{"type": "text", "text": o.text}
	if o.msgCache != "" {
		userBlock["cache_control"] = smokeCacheControl(o.msgCache)
	}
	req := map[string]any{
		"model":      "deepseek-ai/deepseek-v4-pro",
		"max_tokens": o.maxTokens,
		"system":     []any{sysBlock},
		"messages": []any{
			map[string]any{"role": "user", "content": []any{userBlock}},
		},
		"metadata": map[string]any{"user_id": o.userID},
	}
	if o.stream {
		req["stream"] = true
	}
	tools := []any{
		smokeTool("Bash", "Run a shell command", map[string]any{
			"command": map[string]any{"type": "string", "description": "The command to run"},
		}),
		smokeTool("Read", "Read a file from disk", map[string]any{
			"file_path": map[string]any{"type": "string", "description": "Absolute path to the file"},
		}),
		smokeTool("Edit", "Replace a string in a file", map[string]any{
			"file_path":  map[string]any{"type": "string"},
			"old_string": map[string]any{"type": "string"},
			"new_string": map[string]any{"type": "string"},
		}),
	}
	if o.toolCache != "" {
		tools[len(tools)-1].(map[string]any)["cache_control"] = smokeCacheControl(o.toolCache)
	}
	for _, tl := range o.customTools {
		tools = append(tools, tl)
	}
	for i := 0; i < o.cachedTools; i++ {
		tl := smokeTool(fmt.Sprintf("ExtraTool%c", 'A'+i), "Extra cached tool", map[string]any{
			"arg": map[string]any{"type": "string"},
		})
		tl["cache_control"] = smokeCacheControl("5m")
		tools = append(tools, tl)
	}
	req["tools"] = tools
	out, err := json.Marshal(req)
	require.NoError(t, err)
	return out
}

func smokeTool(name, desc string, props map[string]any) map[string]any {
	return map[string]any{
		"name":        name,
		"description": desc,
		"input_schema": map[string]any{
			"type":       "object",
			"properties": props,
		},
	}
}

func smokeCacheControl(ttl string) map[string]any {
	cc := map[string]any{"type": "ephemeral"}
	if ttl != "" {
		cc["ttl"] = ttl
	}
	return cc
}

func applySmokeModelField(body []byte, model string) []byte {
	if model == "" {
		return body
	}
	out, err := sjson.SetBytes(body, "model", model)
	if err != nil {
		return body
	}
	return out
}

func smokeRequestKey(method, path string, body []byte) string {
	h := sha256.New()
	h.Write([]byte(method))
	h.Write([]byte{0})
	h.Write([]byte(path))
	h.Write([]byte{0})
	for _, field := range []string{"prompt_cache_key"} {
		if !gjson.GetBytes(body, field).Exists() {
			continue
		}
		out, err := sjson.DeleteBytes(body, field)
		if err == nil {
			body = out
		}
	}
	h.Write(body)
	return hex.EncodeToString(h.Sum(nil))
}

func buildResponsesJSON(u smokeUsageSpec, toolCall bool, model, text string) string {
	if toolCall {
		return buildResponsesToolJSON(u, model)
	}
	details := usageDetails(u)
	return fmt.Sprintf(`{"id":"resp_smoke","object":"response","status":"completed","model":%q,"output":[{"type":"message","role":"assistant","content":[{"type":"output_text","text":%q}]}],"usage":{"input_tokens":%d,"output_tokens":%d%s}}`,
		model, text, u.input, u.output, details)
}

func buildResponsesToolJSON(u smokeUsageSpec, model string) string {
	details := usageDetails(u)
	return fmt.Sprintf(`{"id":"resp_smoke","object":"response","status":"completed","model":%q,"output":[{"type":"function_call","call_id":"call_smoke","name":"Bash","arguments":"{\"command\":\"ls -la\"}"}],"usage":{"input_tokens":%d,"output_tokens":%d%s}}`,
		model, u.input, u.output, details)
}

func buildResponsesStream(u smokeUsageSpec, toolCall bool, model, text string) string {
	details := usageDetails(u)
	if toolCall {
		return strings.Join([]string{
			"data: {\"type\":\"response.created\",\"response\":{\"id\":\"resp_smoke\",\"status\":\"in_progress\"}}\n",
			"",
			"data: {\"type\":\"response.output_item.done\",\"output_index\":0,\"item\":{\"id\":\"fc_1\",\"type\":\"function_call\",\"call_id\":\"call_smoke\",\"name\":\"Bash\",\"arguments\":\"{\\\"command\\\":\\\"ls -la\\\"}\"}}\n",
			"",
			fmt.Sprintf("data: {\"type\":\"response.completed\",\"response\":{\"id\":\"resp_smoke\",\"status\":\"completed\",\"model\":%q,\"output\":[{\"type\":\"function_call\",\"call_id\":\"call_smoke\",\"name\":\"Bash\",\"arguments\":\"{\\\"command\\\":\\\"ls -la\\\"}\"}],\"usage\":{\"input_tokens\":%d,\"output_tokens\":%d%s}}}\n", model, u.input, u.output, details),
			"",
		}, "\n")
	}
	return strings.Join([]string{
		"data: {\"type\":\"response.created\",\"response\":{\"id\":\"resp_smoke\",\"status\":\"in_progress\"}}\n",
		"",
		fmt.Sprintf("data: {\"type\":\"response.output_text.delta\",\"output_index\":0,\"delta\":%q}\n", text),
		"",
		fmt.Sprintf("data: {\"type\":\"response.completed\",\"response\":{\"id\":\"resp_smoke\",\"status\":\"completed\",\"model\":%q,\"output\":[{\"type\":\"message\",\"role\":\"assistant\",\"content\":[{\"type\":\"output_text\",\"text\":%q}]}],\"usage\":{\"input_tokens\":%d,\"output_tokens\":%d%s}}}\n", model, text, u.input, u.output, details),
		"",
	}, "\n")
}

func usageDetails(u smokeUsageSpec) string {
	if u.cached == 0 && u.cacheWrite == 0 {
		return ""
	}
	if u.cached > 0 {
		return fmt.Sprintf(",\"input_tokens_details\":{\"cached_tokens\":%d}", u.cached)
	}
	return fmt.Sprintf(",\"input_tokens_details\":{\"cache_creation_tokens\":%d}", u.cacheWrite)
}
