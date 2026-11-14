package main

import (
	"fmt"
	"net"
	"net/url"
)

func availablePort(preferred int) (int, error) {
	listener, err := net.Listen("tcp", fmt.Sprintf("127.0.0.1:%d", preferred))
	if err != nil {
		listener, err = net.Listen("tcp", "127.0.0.1:0")
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
