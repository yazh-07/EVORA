package main

import "net/url"

func validChatGPTAuthorizationURL(raw string) bool {
	u, err := url.Parse(raw)
	return err == nil && len(raw) <= 16384 && u.Scheme == "https" &&
		u.Host == "auth.openai.com" && u.User == nil && u.Fragment == "" &&
		u.Path == "/api/accounts/authorize" && u.Query().Get("state") != ""
}
