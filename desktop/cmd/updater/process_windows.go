package main

import (
	"errors"
	"os"
	"os/exec"
	"strings"
	"syscall"
	"time"
)

func hide(cmd *exec.Cmd) {
	cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true, CreationFlags: 0x08000000}
}
func waitPID(pid int, timeout time.Duration) error {
	h, e := syscall.OpenProcess(syscall.SYNCHRONIZE, false, uint32(pid))
	if e == syscall.Errno(87) {
		return nil
	}
	if e != nil {
		return e
	}
	defer syscall.CloseHandle(h)
	r, e := syscall.WaitForSingleObject(h, uint32(timeout/time.Millisecond))
	if e != nil {
		return e
	}
	if r != syscall.WAIT_OBJECT_0 {
		return errors.New("application did not close for update")
	}
	return nil
}
func stopChild(pid int) {
	cmd := exec.Command("taskkill.exe", "/PID", fmtPID(pid), "/T", "/F")
	hide(cmd)
	_ = cmd.Run()
}
func cleanEnvironment() []string {
	var env []string
	for _, value := range os.Environ() {
		u := strings.ToUpper(value)
		if !strings.HasPrefix(u, "EVORA_UPDATE_HEALTH_FILE=") && !strings.HasPrefix(u, "EVORA_UPDATE_EXPECTED_VERSION=") {
			env = append(env, value)
		}
	}
	return env
}
