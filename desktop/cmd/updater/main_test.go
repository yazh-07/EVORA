package main

import (
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"testing"
	"time"

	"github.com/yazh-07/evora/desktop/internal/patcher"
)

// Child test executables stand in for the desktop and Python processes, so the
// real helper's shutdown, apply, restart, health, and rollback sequence runs on
// both Windows and Linux without a webview or an installer.
func TestMain(m *testing.M) {
	role := os.Getenv("EVORA_TEST_UPDATE_ROLE")
	if role == "closing" {
		for {
			if _, e := os.Stat(os.Getenv("EVORA_TEST_UPDATE_STOP")); e == nil {
				os.Exit(0)
			}
			time.Sleep(10 * time.Millisecond)
		}
	}
	if role == "restarting" {
		root, _ := os.Executable()
		root = filepath.Dir(root)
		health := os.Getenv("EVORA_UPDATE_HEALTH_FILE")
		if health == "" {
			_ = os.WriteFile(filepath.Join(root, "old-restarted"), []byte(strconv.Itoa(os.Getpid())), 0600)
			os.Exit(0)
		}
		if os.Getenv("EVORA_TEST_UPDATE_FAIL") == "1" {
			os.Exit(4)
		}
		_ = os.WriteFile(filepath.Join(root, "new-pid"), []byte(strconv.Itoa(os.Getpid())), 0600)
		_ = os.WriteFile(health, []byte(fmt.Sprintf(`{"version":%q}`, os.Getenv("EVORA_UPDATE_EXPECTED_VERSION"))), 0600)
		for {
			time.Sleep(time.Second)
		}
	}
	os.Exit(m.Run())
}
func write(t *testing.T, path string, data []byte) {
	t.Helper()
	if e := os.MkdirAll(filepath.Dir(path), 0755); e != nil {
		t.Fatal(e)
	}
	if e := os.WriteFile(path, data, 0700); e != nil {
		t.Fatal(e)
	}
}
func file(t *testing.T, root, name string) patcher.File {
	t.Helper()
	path := filepath.Join(root, filepath.FromSlash(name))
	hash, e := patcher.Hash(path)
	if e != nil {
		t.Fatal(e)
	}
	stat, e := os.Stat(path)
	if e != nil {
		t.Fatal(e)
	}
	return patcher.File{Path: name, SHA: hash, Size: stat.Size()}
}
func inventory(t *testing.T, path, version string, files []patcher.File) string {
	t.Helper()
	data, _ := json.Marshal(patcher.Manifest{Format: 1, Platform: "windows-x64", Version: version, Files: files})
	write(t, path, data)
	hash, _ := patcher.Hash(path)
	return hash
}
func TestRealHelperHealthAndRollback(t *testing.T) {
	for _, fail := range []bool{false, true} {
		t.Run(fmt.Sprintf("fail=%t", fail), func(t *testing.T) {
			root, stage := t.TempDir(), t.TempDir()
			exe, _ := os.Executable()
			binary, e := os.ReadFile(exe)
			if e != nil {
				t.Fatal(e)
			}
			write(t, filepath.Join(root, "EVORA.exe"), binary)
			for _, name := range []string{"evora-updater.exe", "backend/evora.exe", "backend/ui.js"} {
				write(t, filepath.Join(root, filepath.FromSlash(name)), []byte("old "+name))
			}
			files := []patcher.File{}
			for _, name := range []string{"EVORA.exe", "evora-updater.exe", "backend/evora.exe", "backend/ui.js"} {
				files = append(files, file(t, root, name))
			}
			before := files[3].SHA
			baseline := inventory(t, filepath.Join(root, patcher.Installed), "1.3.12", files)
			write(t, filepath.Join(stage, "payload/backend/ui.js"), []byte("updated UI"))
			updated := file(t, filepath.Join(stage, "payload"), "backend/ui.js")
			next := append(append([]patcher.File{}, files[:3]...), updated)
			hash := inventory(t, filepath.Join(stage, "manifest.json"), "1.4.0", next)
			t.Setenv("EVORA_TEST_UPDATE_ROLE", "restarting")
			if fail {
				t.Setenv("EVORA_TEST_UPDATE_FAIL", "1")
			}
			// The owner PID is part of its stop-marker filename; create children before
			// publishing the plan, then tell them where to watch via a rendezvous file.
			rendezvous := filepath.Join(stage, "stop-request")
			start := func() *exec.Cmd {
				cmd := exec.Command(exe)
				cmd.Env = append(cleanEnvironment(), "EVORA_TEST_UPDATE_ROLE=closing", "EVORA_TEST_UPDATE_STOP="+rendezvous)
				if e := cmd.Start(); e != nil {
					t.Fatal(e)
				}
				t.Cleanup(func() { _ = cmd.Process.Kill() })
				return cmd
			}
			owner, backend := start(), start()
			marker := filepath.Join(stage, fmt.Sprintf("stop-%d.update", owner.Process.Pid))
			done := make(chan struct{})
			go func() {
				defer close(done)
				for i := 0; i < 1000; i++ {
					if _, e := os.Stat(marker); e == nil {
						_ = os.WriteFile(rendezvous, []byte("close"), 0600)
						return
					}
					time.Sleep(10 * time.Millisecond)
				}
			}()
			p := patcher.Plan{Root: root, Stage: stage, ManifestHash: hash, BaselineHash: baseline, Changes: []patcher.Change{{File: updated, Before: &before}}, OwnerPID: owner.Process.Pid, BackendPID: backend.Process.Pid, StopMarker: marker, HealthFile: filepath.Join(stage, "health.json"), ResultFile: filepath.Join(stage, "result.json")}
			data, _ := json.Marshal(p)
			path := filepath.Join(stage, "plan.json")
			write(t, path, data)
			// Wait() must reap the simulated old processes on Unix for PID polling.
			go owner.Wait()
			go backend.Wait()
			e = run(path)
			<-done
			content, _ := os.ReadFile(filepath.Join(root, "backend/ui.js"))
			result, _ := os.ReadFile(p.ResultFile)
			if fail {
				if e == nil || string(content) != "old backend/ui.js" {
					t.Fatalf("rollback: %q, %v", content, e)
				}
				for i := 0; i < 100; i++ {
					if _, e := os.Stat(filepath.Join(root, "old-restarted")); e == nil {
						break
					}
					time.Sleep(10 * time.Millisecond)
				}
				if _, e := os.Stat(filepath.Join(root, "old-restarted")); e != nil {
					t.Fatal("old application not restarted")
				}
				pidData, _ := os.ReadFile(filepath.Join(root, "old-restarted"))
				pid, _ := strconv.Atoi(string(pidData))
				if pid > 0 {
					if process, err := os.FindProcess(pid); err == nil {
						_, _ = process.Wait()
					}
				}
				if string(result) != `{"version":"1.4.0","success":false}` {
					t.Fatalf("failure result: %s", result)
				}
			} else {
				if e != nil || string(content) != "updated UI" {
					t.Fatalf("update: %q, %v", content, e)
				}
				if string(result) != `{"version":"1.4.0","success":true}` {
					t.Fatalf("success result: %s", result)
				}
				pidData, _ := os.ReadFile(filepath.Join(root, "new-pid"))
				pid, _ := strconv.Atoi(string(pidData))
				if pid > 0 {
					process, _ := os.FindProcess(pid)
					_ = process.Kill()
					if e := waitPID(pid, 10*time.Second); e != nil {
						t.Fatal(e)
					}
				}
			}
			if _, e := os.Stat(filepath.Join(root, ".evora-update-journal")); !os.IsNotExist(e) {
				t.Fatal("transaction journal not cleaned")
			}
		})
	}
}
