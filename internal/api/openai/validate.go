// Package openai holds HTTP handlers for the OpenAI Chat Completions surface.
package openai

import "github.com/tidwall/gjson"

// validateChatCompletionBody rejects client-input garbage upstream of
// svc.ProxyOpenAIChatCompletion, so a broken body surfaces as a 400 naming
// the offending field rather than a misleading scorer 503.
func validateChatCompletionBody(body []byte) (string, bool) {
	if msgs := gjson.GetBytes(body, "messages"); !msgs.IsArray() || len(msgs.Array()) == 0 {
		return "messages must be a non-empty array.", false
	}
	for _, param := range []string{"max_tokens", "max_completion_tokens"} {
		if mct := gjson.GetBytes(body, param); mct.Exists() && (mct.Type != gjson.Number || mct.Int() <= 0) {
			return param + " must be a positive integer.", false
		}
	}
	return "", true
}

// validateResponsesBody mirrors validateChatCompletionBody for the Responses
// surface, which carries max_output_tokens (projected to
// max_completion_tokens) and input instead of messages.
func validateResponsesBody(body []byte) (string, bool) {
	if mt := gjson.GetBytes(body, "max_output_tokens"); mt.Exists() && (mt.Type != gjson.Number || mt.Int() <= 0) {
		return "max_output_tokens must be a positive integer.", false
	}
	return "", true
}
