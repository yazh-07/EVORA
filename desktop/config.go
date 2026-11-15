package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
)

type Config struct {
	Mode         string `json:"mode"`           // "webview" or "browser"
	Port         int    `json:"port"`           // Backend server port (default 8000)
	AIProvider   string `json:"ai_provider"`    // "ollama" or "openai"
	OllamaURL    string `json:"ollama_url"`     // e.g. "http://127.0.0.1:11434"
	OllamaModel  string `json:"ollama_model"`   // e.g. "llama3.1:8b"
	CloudBaseURL string `json:"cloud_base_url"` // e.g. "https://openrouter.ai/api/v1"
	CloudModel   string `json:"cloud_model"`    // e.g. "openai/gpt-4o-mini"
	CloudAPIKey  string `json:"cloud_api_key"`  // Protected with current-user DPAPI when persisted
}

func DefaultConfig() Config {
	return Config{
		Mode:         "webview",
		Port:         8000,
		AIProvider:   "ollama",
		OllamaURL:    "http://127.0.0.1:11434",
		OllamaModel:  "llama3.1:8b",
		CloudBaseURL: "https://api.openai.com/v1",
		CloudModel:   "gpt-4o-mini",
		CloudAPIKey:  "",
	}
}

func GetConfigPath() string {
	appData := os.Getenv("APPDATA")
	if appData == "" {
		home, _ := os.UserHomeDir()
		return filepath.Join(home, ".evora", "config.json")
	}
	return filepath.Join(appData, "EVORA", "config.json")
}

func LoadConfig() Config {
	cfg := DefaultConfig()
	path := GetConfigPath()

	data, err := os.ReadFile(path)
	if err != nil {
		// Try local directory fallback
		path = "config.json"
		data, err = os.ReadFile(path)
		if err != nil {
			SaveConfig(cfg)
			return cfg
		}
	}

	if err := json.Unmarshal(data, &cfg); err != nil {
		return DefaultConfig()
	}
	protected := strings.HasPrefix(cfg.CloudAPIKey, protectedSecretPrefix)
	secret, err := unprotectConfigSecret(cfg.CloudAPIKey)
	if err != nil {
		cfg.CloudAPIKey = ""
	} else {
		cfg.CloudAPIKey = secret
	}
	if cfg.CloudAPIKey != "" && !protected {
		if err := saveConfigAt(path, cfg); err != nil {
			cfg.CloudAPIKey = ""
		}
	}
	if cfg.Port <= 0 {
		cfg.Port = 8000
	}
	if cfg.Mode == "" {
		cfg.Mode = "webview"
	}
	return cfg
}

func SaveConfig(cfg Config) error { return saveConfigAt(GetConfigPath(), cfg) }

func saveConfigAt(path string, cfg Config) error {
	protected, err := protectConfigSecret(cfg.CloudAPIKey)
	if err != nil {
		return err
	}
	cfg.CloudAPIKey = protected
	dir := filepath.Dir(path)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return err
	}

	data, err := json.MarshalIndent(cfg, "", "  ")
	if err != nil {
		return err
	}
	temporary, err := os.CreateTemp(dir, ".evora-config-*")
	if err != nil {
		return err
	}
	name := temporary.Name()
	defer os.Remove(name)
	if err := temporary.Chmod(0600); err != nil {
		temporary.Close()
		return err
	}
	if _, err := temporary.Write(data); err != nil {
		temporary.Close()
		return err
	}
	if err := temporary.Sync(); err != nil {
		temporary.Close()
		return err
	}
	if err := temporary.Close(); err != nil {
		return err
	}
	return os.Rename(name, path)
}
