package main

import (
	"fmt"
	"net"
	"net/url"
)

func availablePort(preferred int) (int, error) { return availablePortOn("127.0.0.1", preferred) }
func availablePortOn(host string, preferred int) (int, error) {
	listener, err := net.Listen("tcp", net.JoinHostPort(host, fmt.Sprint(preferred)))
	if err != nil {
		listener, err = net.Listen("tcp", net.JoinHostPort(host, "0"))
	}
	if err != nil {
		return 0, err
	}
	defer listener.Close()
	return listener.Addr().(*net.TCPAddr).Port, nil
}

func validChatGPTAuthorizationURL(raw string) bool {
	u, err := url.Parse(raw)
	return err == nil && len(raw) <= 16384 && u.Scheme == "https" &&
		u.Host == "auth.openai.com" && u.User == nil && u.Fragment == "" &&
		u.Path == "/api/accounts/authorize" && u.Query().Get("state") != ""
}
