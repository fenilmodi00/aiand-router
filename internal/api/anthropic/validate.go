package anthropic

import "github.com/tidwall/gjson"

// validateMessagesBody rejects client-input garbage upstream of
// svc.ProxyMessages, so a broken body surfaces as a 400 naming the offending
// field rather than a misleading scorer 503. max_tokens is optional here
// (the proxy injects a default), but a present value must be a positive
// number.
func validateMessagesBody(body []byte) (string, bool) {
	if msgs := gjson.GetBytes(body, "messages"); !msgs.IsArray() || len(msgs.Array()) == 0 {
		return "messages must be a non-empty array.", false
	}
	if mt := gjson.GetBytes(body, "max_tokens"); mt.Exists() && (mt.Type != gjson.Number || mt.Int() <= 0) {
		return "max_tokens must be a positive integer.", false
	}
	return "", true
}
