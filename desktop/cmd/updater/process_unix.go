//go:build !windows

package main

import (
	"errors"
	"os"
	"os/exec"
	"strings"
	"syscall"
	"time"
)

func hide(cmd *exec.Cmd) {}
func waitPID(pid int, timeout time.Duration) error {
	deadline := time.Now().Add(timeout)
	for time.Now().Before(deadline) {
		if syscall.Kill(pid, 0) != nil {
			return nil
		}
		time.Sleep(50 * time.Millisecond)
	}
	return errors.New("application did not close")
}
func stopChild(pid int) {
	p, e := os.FindProcess(pid)
	if e == nil {
		_ = p.Kill()
	}
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
