package main

import (
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"time"

	"github.com/yazh-07/evora/desktop/internal/patcher"
)

func main() {
	planPath := flag.String("plan", "", "verified update plan")
	recoverRoot := flag.String("recover", "", "recover interrupted update")
	flag.Parse()
	var err error
	if *recoverRoot != "" {
		root, _ := filepath.Abs(*recoverRoot)
		var release func()
		release, err = patcher.Lock(root)
		if err == nil {
			defer release()
			err = patcher.Recover(root)
		}
	} else {
		err = run(*planPath)
	}
	if err != nil {
		fmt.Fprintln(os.Stderr, "EVORA update did not complete:", err)
		os.Exit(1)
	}
}
func readPlan(path string) (patcher.Plan, error) {
	var p patcher.Plan
	f, e := os.Open(path)
	if e != nil {
		return p, e
	}
	defer f.Close()
	data, e := io.ReadAll(io.LimitReader(f, 16*1024*1024+1))
	if e != nil || len(data) > 16*1024*1024 {
		return p, errors.New("invalid update plan size")
	}
	e = json.Unmarshal(data, &p)
	return p, e
}
func markerSafe(p patcher.Plan) bool {
	// Control files can only live beside this private update plan. The desktop's
	// shutdown request is derived from its own PID, not an arbitrary JSON path.
	for _, path := range []string{p.HealthFile, p.ResultFile} {
		if filepath.Clean(filepath.Dir(path)) != p.Stage {
			return false
		}
	}
	expected := fmt.Sprintf("stop-%d.update", p.OwnerPID)
	return p.OwnerPID > 0 && p.BackendPID > 0 && filepath.Base(p.StopMarker) == expected
}
func launch(root, health, version string) (*exec.Cmd, error) {
	cmd := exec.Command(filepath.Join(root, "EVORA.exe"))
	cmd.Dir = root
	cmd.Env = cleanEnvironment()
	if health != "" {
		cmd.Env = append(cmd.Env, "EVORA_UPDATE_HEALTH_FILE="+health, "EVORA_UPDATE_EXPECTED_VERSION="+version)
	}
	hide(cmd)
	e := cmd.Start()
	return cmd, e
}
func run(path string) error {
	p, e := readPlan(path)
	if e != nil {
		return e
	}
	if filepath.Clean(filepath.Dir(path)) != p.Stage || !markerSafe(p) {
		return errors.New("invalid update control paths")
	}
	release, e := patcher.Lock(p.Root)
	if e != nil {
		return errors.New("another update is running")
	}
	defer release()
	next, e := patcher.Validate(p)
	if e != nil {
		return e
	}
	result := func(success bool) {
		_ = os.WriteFile(p.ResultFile, []byte(fmt.Sprintf(`{"version":%q,"success":%t}`, next.Version, success)), 0600)
	}
	// Request a graceful desktop shutdown. It also waits for Python and its JVM.
	if e = os.WriteFile(p.StopMarker, []byte("update\n"), 0600); e != nil {
		return e
	}
	if e = waitPID(p.OwnerPID, 150*time.Second); e != nil {
		_ = os.Remove(p.StopMarker)
		return e
	}
	if e = waitPID(p.BackendPID, 30*time.Second); e != nil {
		return e
	}
	rollback := func(cause error) error {
		var err error
		for attempt := 0; attempt < 90; attempt++ {
			err = patcher.Recover(p.Root)
			if err == nil {
				break
			}
			time.Sleep(time.Second)
		}
		if err != nil {
			return fmt.Errorf("recovery required: %w", err)
		}
		result(false)
		_, _ = launch(p.Root, "", "")
		return cause
	}
	if e = patcher.Apply(p); e != nil {
		return rollback(e)
	}
	_ = os.Remove(p.HealthFile)
	cmd, e := launch(p.Root, p.HealthFile, next.Version)
	if e != nil {
		return rollback(e)
	}
	exited := make(chan error, 1)
	go func() { exited <- cmd.Wait() }()
	deadline := time.Now().Add(240 * time.Second)
	for time.Now().Before(deadline) {
		if data, err := os.ReadFile(p.HealthFile); err == nil {
			var value struct {
				Version string `json:"version"`
			}
			if json.Unmarshal(data, &value) == nil && value.Version == next.Version {
				if err = patcher.Commit(p.Root); err != nil {
					return err
				}
				result(true)
				return nil
			}
		}
		select {
		case <-exited:
			return rollback(errors.New("new application stopped before its health check"))
		default:
		}
		time.Sleep(250 * time.Millisecond)
	}
	// Stop only the process tree this helper started, before restoring locked DLLs.
	stopChild(cmd.Process.Pid)
	if e = waitPID(cmd.Process.Pid, 30*time.Second); e != nil {
		return e
	}
	return rollback(errors.New("new application did not pass its health check"))
}
