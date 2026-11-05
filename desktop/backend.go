package main

import (
	"fmt"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strconv"
	"syscall"
	"time"
)

type BackendManager struct {
	cmd    *exec.Cmd
	port   int
	url    string
	dbPath string
	vault  string
}

func NewBackendManager(cfg Config) *BackendManager {
	appData := os.Getenv("APPDATA")
	var baseDataDir string
	if appData != "" {
		baseDataDir = filepath.Join(appData, "EVORA", "data")
	} else {
		home, _ := os.UserHomeDir()
		baseDataDir = filepath.Join(home, ".evora", "data")
	}

	return &BackendManager{
		port:   cfg.Port,
		url:    fmt.Sprintf("http://127.0.0.1:%d", cfg.Port),
		dbPath: filepath.Join(baseDataDir, "cases.sqlite3"),
		vault:  filepath.Join(baseDataDir, "vault"),
	}
}

func (b *BackendManager) findExecutable() (string, error) {
	exeName := "evora"
	if runtime.GOOS == "windows" {
		exeName = "evora.exe"
	}

	candidates := []string{
		filepath.Join("backend", exeName),
		exeName,
		filepath.Join("..", "backend", exeName),
		filepath.Join(".", "_internal", exeName),
	}

	execPath, err := os.Executable()
	if err == nil {
		execDir := filepath.Dir(execPath)
		candidates = append([]string{
			filepath.Join(execDir, "backend", exeName),
			filepath.Join(execDir, exeName),
		}, candidates...)
	}

	for _, c := range candidates {
		if info, err := os.Stat(c); err == nil && !info.IsDir() {
			return filepath.Abs(c)
		}
	}

	return "", fmt.Errorf("EVORA backend executable '%s' not found", exeName)
}

func (b *BackendManager) Start(cfg Config) error {
	binPath, err := b.findExecutable()
	if err != nil {
		return err
	}

	_ = os.MkdirAll(filepath.Dir(b.dbPath), 0755)
	_ = os.MkdirAll(b.vault, 0755)

	args := []string{
		"--no-browser",
		"--port", strconv.Itoa(b.port),
		"--database", b.dbPath,
		"--storage", b.vault,
	}

	cmd := exec.Command(binPath, args...)
	cmd.Dir = filepath.Dir(binPath)

	// Inherit system environment and append AI configurations
	cmd.Env = os.Environ()
	if cfg.AIProvider == "openai" {
		cmd.Env = append(cmd.Env,
			"EVORA_QA_PROVIDER=openai",
			"OPENAI_BASE_URL="+cfg.CloudBaseURL,
			"OPENAI_API_KEY="+cfg.CloudAPIKey,
			"EVORA_QA_MODEL="+cfg.CloudModel,
		)
	} else {
		cmd.Env = append(cmd.Env,
			"EVORA_QA_PROVIDER=ollama",
			"EVORA_QA_URL="+cfg.OllamaURL,
			"EVORA_QA_MODEL="+cfg.OllamaModel,
		)
	}

	// On Windows, hide command window completely
	hideWindow(cmd)

	if err := cmd.Start(); err != nil {
		return fmt.Errorf("failed to start backend process: %w", err)
	}
	b.cmd = cmd
	return nil
}

func (b *BackendManager) WaitReady(timeout time.Duration) bool {
	deadline := time.Now().Add(timeout)
	client := http.Client{Timeout: 500 * time.Millisecond}

	for time.Now().Before(deadline) {
		resp, err := client.Get(b.url + "/")
		if err == nil && resp.StatusCode == 200 {
			_ = resp.Body.Close()
			return true
		}
		time.Sleep(200 * time.Millisecond)
	}
	return false
}

func (b *BackendManager) Stop() {
	if b.cmd != nil && b.cmd.Process != nil {
		_ = b.cmd.Process.Kill()
		_ = b.cmd.Wait()
	}
}

// hideWindow sets SysProcAttr to avoid popping up a console window
func hideWindow(cmd *exec.Cmd) {
	if runtime.GOOS == "windows" {
		cmd.SysProcAttr = &syscall.SysProcAttr{
			HideWindow:    true,
			CreationFlags: 0x08000000, // CREATE_NO_WINDOW
		}
	}
}
