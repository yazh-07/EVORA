//go:build !windows

package main

import (
	"errors"
	"fmt"
	"os"
	"os/exec"
	"runtime"
	"strings"
	"syscall"
	"time"
)

func hide(cmd *exec.Cmd) { cmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true} }
func waitPID(pid int, timeout time.Duration) error {
	deadline := time.Now().Add(timeout)
	for time.Now().Before(deadline) {
		err := syscall.Kill(pid, 0)
		if err == syscall.ESRCH {
			return nil
		}
		if runtime.GOOS == "linux" {
			data, e := os.ReadFile(fmt.Sprintf("/proc/%d/stat", pid))
			if os.IsNotExist(e) {
				return nil
			}
			if i := strings.LastIndex(string(data), ") "); i >= 0 && i+2 < len(data) && (data[i+2] == 'Z' || data[i+2] == 'X') {
				return nil
			}
		}
		time.Sleep(50 * time.Millisecond)
	}
	return errors.New("application did not close")
}
func stopChild(pid int) {
	_ = syscall.Kill(-pid, syscall.SIGTERM)
	if waitPID(pid, 5*time.Second) != nil {
		_ = syscall.Kill(-pid, syscall.SIGKILL)
	}
	// A supervisor may have exited before a stuck child. Kill the private group.
	_ = syscall.Kill(-pid, syscall.SIGKILL)
}
func cleanEnvironment() []string {
	var env []string
	for _, value := range os.Environ() {
		if !strings.HasPrefix(value, "EVORA_UPDATE_HEALTH_FILE=") && !strings.HasPrefix(value, "EVORA_UPDATE_EXPECTED_VERSION=") {
			env = append(env, value)
		}
	}
	return env
}
