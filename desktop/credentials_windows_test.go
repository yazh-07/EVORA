package main

import (
	"bytes"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestDesktopAPIKeyIsProtectedAndLegacyConfigMigrates(t *testing.T) {
	root := t.TempDir()
	t.Setenv("APPDATA", root)
	cfg := DefaultConfig()
	cfg.CloudAPIKey = "synthetic-config-key-unique"
	if err := SaveConfig(cfg); err != nil {
		t.Fatal(err)
	}
	raw, err := os.ReadFile(GetConfigPath())
	if err != nil {
		t.Fatal(err)
	}
	if bytes.Contains(raw, []byte(cfg.CloudAPIKey)) || !bytes.Contains(raw, []byte(protectedSecretPrefix)) {
		t.Fatal("API key was not protected")
	}
	if got := LoadConfig(); got.CloudAPIKey != cfg.CloudAPIKey {
		t.Fatal("protected key failed round trip")
	}
	legacy := `{"mode":"webview","cloud_api_key":"synthetic-config-key-unique"}`
	if err := os.WriteFile(GetConfigPath(), []byte(legacy), 0600); err != nil {
		t.Fatal(err)
	}
	if got := LoadConfig(); got.CloudAPIKey != cfg.CloudAPIKey {
		t.Fatal("legacy key was lost")
	}
	migrated, _ := os.ReadFile(GetConfigPath())
	if bytes.Contains(migrated, []byte(cfg.CloudAPIKey)) {
		t.Fatal("legacy key remained plaintext")
	}
}
func TestCorruptProtectedKeyNeverBecomesAnAPIKey(t *testing.T) {
	t.Setenv("APPDATA", t.TempDir())
	path := GetConfigPath()
	os.MkdirAll(filepath.Dir(path), 0700)
	os.WriteFile(path, []byte(`{"cloud_api_key":"`+protectedSecretPrefix+`invalid"}`), 0600)
	if got := LoadConfig(); got.CloudAPIKey != "" {
		t.Fatal("corrupt ciphertext exposed as an API key")
	}
	if _, err := unprotectConfigSecret(protectedSecretPrefix + strings.Repeat("A", 20)); err == nil {
		t.Fatal("invalid protected key accepted")
	}
}
