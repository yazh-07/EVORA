package main

import (
	"bufio"
	"fmt"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"
)

type DiagnosticInfo struct {
	BinPath    string
	BinExists  bool
	Port       int
	URL        string
	LastError  string
	LogPath    string
	RecentLogs string
}

type BackendManager struct {
	mu        sync.Mutex
	cmd       *exec.Cmd
	port      int
	url       string
	dbPath    string
	vault     string
	logPath   string
	binPath   string
	lastError string
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

	logPath := filepath.Join(filepath.Dir(baseDataDir), "backend.log")

	return &BackendManager{
		port:    cfg.Port,
		url:     fmt.Sprintf("http://127.0.0.1:%d", cfg.Port),
		dbPath:  filepath.Join(baseDataDir, "cases.sqlite3"),
		vault:   filepath.Join(baseDataDir, "vault"),
		logPath: logPath,
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
			abs, _ := filepath.Abs(c)
			b.binPath = abs
			return abs, nil
		}
	}

	// Save best guess path for diagnostics
	if len(candidates) > 0 {
		b.binPath, _ = filepath.Abs(candidates[0])
	}
	return "", fmt.Errorf("backend executable '%s' not found. It may have been blocked or quarantined by your antivirus (Windows Defender)", exeName)
}

func (b *BackendManager) Start(cfg Config) error {
	b.mu.Lock()
	defer b.mu.Unlock()

	b.lastError = ""
	binPath, err := b.findExecutable()
	if err != nil {
		b.lastError = err.Error()
		return err
	}

	_ = os.MkdirAll(filepath.Dir(b.dbPath), 0755)
	_ = os.MkdirAll(b.vault, 0755)
	_ = os.MkdirAll(filepath.Dir(b.logPath), 0755)

	logFile, err := os.OpenFile(b.logPath, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0644)
	if err != nil {
		fmt.Printf("[EVORA] Warning: could not open log file: %v\n", err)
	}

	args := []string{
		"--no-browser",
		"--port", strconv.Itoa(b.port),
		"--database", b.dbPath,
		"--storage", b.vault,
	}

	cmd := exec.Command(binPath, args...)
	cmd.Dir = filepath.Dir(binPath)

	if logFile != nil {
		cmd.Stdout = logFile
		cmd.Stderr = logFile
	}

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

	hideWindow(cmd)

	if err := cmd.Start(); err != nil {
		b.lastError = fmt.Sprintf("Failed to launch '%s': %v", binPath, err)
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
		if err == nil && (resp.StatusCode == 200 || resp.StatusCode == 404) {
			_ = resp.Body.Close()
			return true
		}
		time.Sleep(200 * time.Millisecond)
	}
	return false
}

func (b *BackendManager) Stop() {
	b.mu.Lock()
	defer b.mu.Unlock()
	if b.cmd != nil && b.cmd.Process != nil {
		_ = b.cmd.Process.Kill()
		_ = b.cmd.Wait()
		b.cmd = nil
	}
}

func (b *BackendManager) GetDiagnosticInfo() DiagnosticInfo {
	b.mu.Lock()
	defer b.mu.Unlock()

	binExists := false
	if b.binPath != "" {
		if fi, err := os.Stat(b.binPath); err == nil && !fi.IsDir() {
			binExists = true
		}
	}

	recentLogs := ""
	if b.logPath != "" {
		recentLogs = readTail(b.logPath, 25)
	}

	return DiagnosticInfo{
		BinPath:    b.binPath,
		BinExists:  binExists,
		Port:       b.port,
		URL:        b.url,
		LastError:  b.lastError,
		LogPath:    b.logPath,
		RecentLogs: recentLogs,
	}
}

func readTail(path string, lines int) string {
	f, err := os.Open(path)
	if err != nil {
		return "Log file empty or not yet created."
	}
	defer f.Close()

	var collected []string
	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		collected = append(collected, scanner.Text())
		if len(collected) > lines {
			collected = collected[1:]
		}
	}
	if len(collected) == 0 {
		return "Log file contains no error output."
	}
	return strings.Join(collected, "\n")
}

func hideWindow(cmd *exec.Cmd) {
	if runtime.GOOS == "windows" {
		cmd.SysProcAttr = &syscall.SysProcAttr{
			HideWindow:    true,
			CreationFlags: 0x08000000, // CREATE_NO_WINDOW
		}
	}
}
