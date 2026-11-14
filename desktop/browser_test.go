package main

import (
	"net"
	"testing"
)

func TestOccupiedPortIsNotReused(t *testing.T) {
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	defer listener.Close()
	oldPort := listener.Addr().(*net.TCPAddr).Port
	selected, err := availablePort(oldPort)
	if err != nil || selected == oldPort {
		t.Fatal("must not attach to the occupied old endpoint")
	}
}

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
