package main

import (
	"encoding/base64"
	"errors"
	"golang.org/x/sys/windows"
	"strings"
	"unsafe"
)

const protectedSecretPrefix = "dpapi-user-v1:"

func protectConfigSecret(secret string) (string, error) {
	if secret == "" {
		return "", nil
	}
	raw := []byte(secret)
	input := windows.DataBlob{Size: uint32(len(raw)), Data: &raw[0]}
	var output windows.DataBlob
	if err := windows.CryptProtectData(&input, nil, nil, 0, nil, 1, &output); err != nil {
		return "", errors.New("could not protect desktop API key")
	}
	defer windows.LocalFree(windows.Handle(uintptr(unsafe.Pointer(output.Data))))
	encoded := base64.StdEncoding.EncodeToString(unsafe.Slice(output.Data, output.Size))
	return protectedSecretPrefix + encoded, nil
}
func unprotectConfigSecret(secret string) (string, error) {
	if !strings.HasPrefix(secret, protectedSecretPrefix) {
		return secret, nil
	}
	raw, err := base64.StdEncoding.DecodeString(strings.TrimPrefix(secret, protectedSecretPrefix))
	if err != nil || len(raw) == 0 {
		return "", errors.New("invalid protected desktop API key")
	}
	input := windows.DataBlob{Size: uint32(len(raw)), Data: &raw[0]}
	var output windows.DataBlob
	if err := windows.CryptUnprotectData(&input, nil, nil, 0, nil, 1, &output); err != nil {
		return "", errors.New("could not unlock desktop API key")
	}
	defer windows.LocalFree(windows.Handle(uintptr(unsafe.Pointer(output.Data))))
	return string(unsafe.Slice(output.Data, output.Size)), nil
}
