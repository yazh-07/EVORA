package main

import "testing"

func TestSignInDestination(t *testing.T) {
	if !validChatGPTAuthorizationURL("https://auth.openai.com/api/accounts/authorize?state=example") {
		t.Fatal("official destination rejected")
	}
	for _, raw := range []string{"https://auth.openai.com.evil.test/api/accounts/authorize?state=x", "https://user@auth.openai.com/api/accounts/authorize?state=x", "http://auth.openai.com/api/accounts/authorize?state=x", "https://auth.openai.com:443/api/accounts/authorize?state=x", "file:///tmp/test", "javascript:alert(1)", "https://auth.openai.com/api/accounts/authorize"} {
		if validChatGPTAuthorizationURL(raw) {
			t.Fatalf("accepted invalid destination %q", raw)
		}
	}
}
